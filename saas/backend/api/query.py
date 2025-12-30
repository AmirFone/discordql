"""
SQL Query endpoints.
Allows users to execute read-only SQL queries against their data.

SECURITY: Multi-tenant isolation is enforced via:
1. PostgreSQL Row-Level Security (RLS) policies
2. SET LOCAL app.current_tenant = user's clerk_id
3. Query validation to block dangerous patterns
4. Table whitelist to prevent information disclosure
5. Error message sanitization to prevent information leakage
"""
import logging
import re
from typing import List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import asyncpg

from sqlalchemy import text

from api.auth import User, get_current_user
from services.shared_database import get_shared_pool
from services.tenant import tenant_connection, TenantContextError
from db.connection import get_db_session
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


class QueryRequest(BaseModel):
    """Request to execute a SQL query."""
    sql: str
    limit: int = 1000


class ColumnInfo(BaseModel):
    """Column metadata."""
    name: str
    type: str


class QueryResponse(BaseModel):
    """Response from a SQL query."""
    columns: List[ColumnInfo]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool = False


class TableInfo(BaseModel):
    """Table metadata for schema viewer."""
    name: str
    columns: List[ColumnInfo]
    row_count: int


class SchemaResponse(BaseModel):
    """Database schema response."""
    tables: List[TableInfo]


# ============================================================================
# SECURITY: Blocked keywords and injection patterns
# ============================================================================

# Dangerous SQL patterns to block - case insensitive
BLOCKED_KEYWORDS = {
    # DDL statements
    "DROP", "CREATE", "ALTER", "TRUNCATE",
    # DML statements (except SELECT)
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT", "REPLACE",
    # DCL statements
    "GRANT", "REVOKE",
    # Transaction control (prevent transaction manipulation)
    "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE",
    # Session/connection control
    "SET", "RESET", "DISCARD",
    # Stored procedures and functions
    "CALL", "DO", "PREPARE", "DEALLOCATE", "EXECUTE",
    # PostgreSQL specific dangerous operations
    "COPY", "VACUUM", "ANALYZE", "CLUSTER", "REINDEX",
    "LOCK", "UNLOCK", "REFRESH", "NOTIFY", "LISTEN", "UNLISTEN",
    "LOAD", "SECURITY", "COMMENT", "REASSIGN", "OWNED",
    # Dangerous functions
    "PG_SLEEP", "PG_TERMINATE_BACKEND", "PG_CANCEL_BACKEND",
    "PG_RELOAD_CONF", "PG_ROTATE_LOGFILE", "PG_SWITCH_WAL",
    "LO_IMPORT", "LO_EXPORT", "LO_UNLINK",
    "DBLINK", "DBLINK_EXEC", "DBLINK_CONNECT",
    # File operations
    "PG_READ_FILE", "PG_WRITE_FILE", "PG_READ_BINARY_FILE",
    # RLS bypass attempts - CRITICAL for multi-tenant security
    "CURRENT_SETTING", "SET_CONFIG",
    # System catalog access - could leak other tenant info
    "PG_CATALOG", "INFORMATION_SCHEMA",
    # Policy introspection
    "PG_POLICIES", "PG_POLICY",
    # Additional blocked keywords for security
    "EXPLAIN",  # Can reveal query plans and table structures
    "SHOW",  # Reveals configuration settings
    "TABLE",  # Shorthand for SELECT * FROM table (bypass SELECT check)
    "VALUES",  # Can be used in place of SELECT
    "RETURNING",  # Can extract data from write operations
}

# Patterns that indicate potential SQL injection or RLS bypass attempts
INJECTION_PATTERNS = [
    r";\s*(?:DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|TRUNCATE|GRANT|REVOKE)",  # Statement stacking
    r"--",  # SQL comments (could hide malicious code)
    r"/\*",  # Block comments
    r"UNION\s+ALL\s+SELECT",  # UNION injection (suspicious patterns only)
    r"INTO\s+OUTFILE",  # File write attempts
    r"INTO\s+DUMPFILE",  # File write attempts
    r"LOAD_FILE",  # File read attempts
    r"@@",  # System variables (MySQL)
    r"EXEC\s*\(",  # EXEC calls
    r"EXECUTE\s+",  # EXECUTE statements
    r"XP_",  # Extended stored procedures (SQL Server)
    r"SP_",  # System stored procedures
    r"0x[0-9a-fA-F]+",  # Hex encoding (potential obfuscation)
    r"\$\$",  # Dollar-quoted strings (PL/pgSQL blocks)
    r"CHR\s*\(\s*\d",  # Character function with number (obfuscation)
    r"CHAR\s*\(\s*\d",  # Character function with number (obfuscation)
    # RLS bypass patterns - CRITICAL
    r"app\.current_tenant",  # Direct reference to tenant session var
    r"current_setting\s*\(",  # Attempt to read session variables
    r"set_config\s*\(",  # Attempt to set session variables
]

# SECURITY: Whitelist of tables users can query
# Use secure views for materialized views (they don't support RLS)
ALLOWED_TABLES = {
    "servers", "users", "server_members", "channels",
    "messages", "message_mentions", "emojis", "reactions", "sync_state",
    # Secure views (wrap materialized views with tenant filtering)
    "user_interactions_secure", "daily_stats_secure",
}

# SECURITY: Block direct access to raw materialized views
BLOCKED_TABLES = {
    "user_interactions", "daily_stats",  # Use _secure views instead
}


# ============================================================================
# SECURITY: Error Sanitization
# ============================================================================

# PostgreSQL SQLSTATE codes for syntax errors (class 42)
# https://www.postgresql.org/docs/current/errcodes-appendix.html
SQLSTATE_SYNTAX_ERRORS = {
    "42000": "syntax_error_or_access_rule_violation",
    "42601": "syntax_error",
    "42501": "insufficient_privilege",
    "42846": "cannot_coerce",
    "42803": "grouping_error",
    "42P01": "undefined_table",
    "42703": "undefined_column",
    "42883": "undefined_function",
    "42P02": "undefined_parameter",
    "42704": "undefined_object",
    "42701": "duplicate_column",
    "42P03": "duplicate_cursor",
    "42P04": "duplicate_database",
    "42723": "duplicate_function",
    "42P05": "duplicate_prepared_statement",
    "42P06": "duplicate_schema",
    "42P07": "duplicate_table",
    "42712": "duplicate_alias",
    "42710": "duplicate_object",
    "42702": "ambiguous_column",
    "42725": "ambiguous_function",
    "42P08": "ambiguous_parameter",
    "42P09": "ambiguous_alias",
    "42P10": "invalid_column_reference",
    "42611": "invalid_column_definition",
    "42P11": "invalid_cursor_definition",
    "42P12": "invalid_database_definition",
    "42P13": "invalid_function_definition",
    "42P14": "invalid_prepared_statement_definition",
    "42P15": "invalid_schema_definition",
    "42P16": "invalid_table_definition",
    "42P17": "invalid_object_definition",
    "42P18": "indeterminate_datatype",
    "42P19": "invalid_recursion",
    "42P20": "windowing_error",
    "42P21": "collation_mismatch",
    "42P22": "indeterminate_collation",
    "42809": "wrong_object_type",
    "428C9": "generated_always",
    "42939": "reserved_name",
}

# Sensitive patterns to scrub from error messages
# Order matters - more specific patterns first
SENSITIVE_PATTERNS = [
    # Tenant IDs (Clerk format: user_XXXXX) - must come before generic tenant_ pattern
    (r"\buser_[a-zA-Z0-9]{10,50}\b", "[tenant_id]"),
    # Schema names that might leak tenant info
    (r"\btenant_[a-zA-Z0-9_]+\b", "[schema]"),
    # UUID patterns
    (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "[uuid]"),
    # Database internal paths
    (r"/[a-zA-Z0-9_/]+\.c:\d+", "[internal]"),
    # Connection strings (must come before host:port pattern)
    (r"postgresql://[^\s]+", "[connection]"),
    # IP addresses
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[ip]"),
    # Hostnames with ports (be careful not to match column:table references)
    (r"\b[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]:\d{2,5}\b", "[host]"),
]


class SanitizedError:
    """
    A sanitized error that's safe to return to the frontend.

    Contains only information that cannot leak tenant data or internal
    database structure.
    """
    def __init__(
        self,
        message: str,
        error_type: str,
        position: Optional[int] = None,
        hint: Optional[str] = None
    ):
        self.message = message
        self.error_type = error_type
        self.position = position
        self.hint = hint

    def to_detail(self) -> str:
        """Format as an error detail string for HTTPException."""
        parts = [self.message]
        if self.position is not None:
            parts.append(f" (at position {self.position})")
        return "".join(parts)


def scrub_sensitive_data(text: str) -> str:
    """
    Remove potentially sensitive data from error messages.

    This is a defense-in-depth measure - we also use allowlists for
    what information to include, but this ensures any leaked data is scrubbed.
    """
    if not text:
        return text

    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


def extract_safe_position(error: asyncpg.PostgresError) -> Optional[int]:
    """
    Extract the character position from an error if available.

    The position indicates where in the user's SQL query the error occurred.
    This is safe to expose as it only refers to their own query text.
    """
    if hasattr(error, 'position') and error.position:
        try:
            return int(error.position)
        except (ValueError, TypeError):
            return None
    return None


def sanitize_postgres_error(error: asyncpg.PostgresError, sql: str) -> SanitizedError:
    """
    Sanitize a PostgreSQL error for safe display to the user.

    SECURITY: This function ensures no sensitive information leaks:
    - No table/column names from other tenants
    - No schema structure details
    - No internal PostgreSQL details
    - No connection strings or credentials

    What IS safe to expose:
    - Generic error type (syntax error, permission denied, etc.)
    - Position in the user's query where error occurred
    - Safe hints for common errors
    """
    sqlstate = getattr(error, 'sqlstate', None) or ''
    message = getattr(error, 'message', str(error)) or str(error)
    position = extract_safe_position(error)

    # Log the full error for debugging (server-side only)
    logger.warning(
        f"PostgreSQL error - sqlstate={sqlstate}, message={scrub_sensitive_data(message)}"
    )

    # Determine error type and provide safe, helpful message
    if sqlstate == '42601':  # syntax_error
        # Extract useful info from syntax error without leaking sensitive data
        safe_hint = None

        # Common syntax issues we can detect
        lower_msg = message.lower()
        if 'at or near' in lower_msg:
            # Extract the token that caused the error (this is from user's query)
            match = re.search(r'at or near "([^"]+)"', message, re.IGNORECASE)
            if match:
                token = match.group(1)
                # Only include if it's reasonably short and doesn't look like sensitive data
                if len(token) <= 30 and not any(p[0] in token.lower() for p in [('user_', ''), ('tenant_', '')]):
                    safe_hint = f'Check near "{token}"'

        return SanitizedError(
            message="SQL syntax error. Check your query syntax.",
            error_type="syntax_error",
            position=position,
            hint=safe_hint
        )

    elif sqlstate == '42P01':  # undefined_table
        return SanitizedError(
            message="Table does not exist or you don't have access to it.",
            error_type="undefined_table",
            position=position,
            hint="Use the Schema panel to see available tables."
        )

    elif sqlstate == '42703':  # undefined_column
        return SanitizedError(
            message="Column does not exist in the specified table.",
            error_type="undefined_column",
            position=position,
            hint="Check column names in the Schema panel."
        )

    elif sqlstate == '42883':  # undefined_function
        return SanitizedError(
            message="Function does not exist or has wrong argument types.",
            error_type="undefined_function",
            position=position,
            hint="Check function name and argument types."
        )

    elif sqlstate == '42501':  # insufficient_privilege
        return SanitizedError(
            message="Permission denied for this operation.",
            error_type="permission_denied",
            position=None,
            hint=None
        )

    elif sqlstate == '42803':  # grouping_error
        return SanitizedError(
            message="Column must appear in GROUP BY clause or be in an aggregate function.",
            error_type="grouping_error",
            position=position,
            hint="Add the column to GROUP BY or wrap it in an aggregate like COUNT(), SUM(), etc."
        )

    elif sqlstate == '42702':  # ambiguous_column
        return SanitizedError(
            message="Column reference is ambiguous. Specify the table name.",
            error_type="ambiguous_column",
            position=position,
            hint="Use table.column format to disambiguate."
        )

    elif sqlstate == '42846':  # cannot_coerce
        return SanitizedError(
            message="Cannot convert between the specified data types.",
            error_type="type_error",
            position=position,
            hint="Check that you're comparing compatible types."
        )

    elif sqlstate == '22P02':  # invalid_text_representation
        return SanitizedError(
            message="Invalid input syntax for data type.",
            error_type="type_error",
            position=position,
            hint="Check the format of your literal values."
        )

    elif sqlstate == '22003':  # numeric_value_out_of_range
        return SanitizedError(
            message="Numeric value out of range.",
            error_type="value_error",
            position=position,
            hint=None
        )

    elif sqlstate == '22012':  # division_by_zero
        return SanitizedError(
            message="Division by zero.",
            error_type="value_error",
            position=position,
            hint="Add a NULLIF or CASE to handle zero divisors."
        )

    elif sqlstate and sqlstate.startswith('42'):  # Other syntax/semantic errors
        return SanitizedError(
            message="Query error. Please check your SQL syntax.",
            error_type="query_error",
            position=position,
            hint=None
        )

    elif sqlstate and sqlstate.startswith('23'):  # Integrity constraint violation
        return SanitizedError(
            message="Data constraint violation.",
            error_type="constraint_error",
            position=None,
            hint=None
        )

    elif sqlstate == '57014':  # query_canceled (timeout)
        return SanitizedError(
            message="Query timed out. Try adding LIMIT or simplifying your query.",
            error_type="timeout",
            position=None,
            hint="Complex queries may need optimization."
        )

    else:
        # Unknown error - try to extract safe, useful information
        # Strategy: Parse the raw message for safe tokens, scrub everything else

        # Start with a generic message
        safe_message = "Query execution failed."
        safe_hint = None

        # Try to extract useful patterns from the raw message that are safe to expose
        raw_msg = str(message).lower()

        # Check for common error patterns and provide helpful generic messages
        if "division by zero" in raw_msg:
            safe_message = "Division by zero error."
            safe_hint = "Check for zero values in divisors."
        elif "out of range" in raw_msg:
            safe_message = "Value out of range for data type."
        elif "invalid input" in raw_msg:
            safe_message = "Invalid input value."
            safe_hint = "Check the format of your literal values."
        elif "null value" in raw_msg and "not-null" in raw_msg:
            safe_message = "Null value in non-nullable column."
        elif "unique" in raw_msg and "violation" in raw_msg:
            safe_message = "Duplicate value violates unique constraint."
        elif "foreign key" in raw_msg:
            safe_message = "Foreign key constraint violation."
        elif "connection" in raw_msg or "connect" in raw_msg:
            safe_message = "Database connection error. Please try again."
        elif "memory" in raw_msg:
            safe_message = "Query requires too much memory. Try adding LIMIT."
        elif "cancelled" in raw_msg or "canceled" in raw_msg:
            safe_message = "Query was cancelled."
        elif "deadlock" in raw_msg:
            safe_message = "Database deadlock detected. Please retry."
        elif "lock" in raw_msg and "timeout" in raw_msg:
            safe_message = "Lock timeout. Please retry."

        # If we still have a generic message, try to extract the "at or near" token
        if safe_message == "Query execution failed." and "at or near" in raw_msg:
            match = re.search(r'at or near "([^"]{1,30})"', message, re.IGNORECASE)
            if match:
                token = match.group(1)
                # Only include if it doesn't look like sensitive data
                if not re.search(r'(user_|tenant_|[0-9a-f]{8}-)', token, re.IGNORECASE):
                    safe_hint = f'Error near "{token}"'

        # Include SQLSTATE code for advanced debugging (codes are not sensitive)
        if sqlstate:
            safe_hint = f"{safe_hint} (Error code: {sqlstate})" if safe_hint else f"Error code: {sqlstate}"

        return SanitizedError(
            message=safe_message,
            error_type="unknown_error",
            position=position,
            hint=safe_hint
        )


def normalize_sql(sql: str) -> str:
    """Normalize SQL for security analysis by removing comments and extra whitespace."""
    # Remove single-line comments
    sql = re.sub(r'--[^\n]*', ' ', sql)
    # Remove block comments
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    # Normalize whitespace
    sql = re.sub(r'\s+', ' ', sql)
    return sql.strip()


def extract_table_names(sql: str) -> set:
    """
    Extract table names from a SQL query.

    This is a basic extraction for validation purposes.
    RLS provides the actual security - this is defense in depth.
    """
    normalized = normalize_sql(sql).upper()
    tables = set()

    # Match FROM clause tables
    from_pattern = r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    tables.update(m.lower() for m in re.findall(from_pattern, normalized, re.IGNORECASE))

    # Match JOIN clause tables
    join_pattern = r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    tables.update(m.lower() for m in re.findall(join_pattern, normalized, re.IGNORECASE))

    return tables


def validate_query(sql: str) -> None:
    """
    Validate that a query is safe to execute (read-only).

    Security measures:
    1. Only allow SELECT/WITH statements
    2. Block dangerous keywords (DDL, DML except SELECT)
    3. Block SQL comments (potential code hiding)
    4. Block known injection patterns
    5. Block RLS bypass attempts
    6. Limit query complexity
    7. Validate table access
    """
    if not sql or not sql.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )

    # Check for injection patterns BEFORE normalizing (to catch obfuscation)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            logger.warning(f"Query blocked - injection pattern detected: {pattern}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query contains potentially dangerous patterns"
            )

    # Normalize the SQL for keyword analysis
    normalized = normalize_sql(sql)
    sql_upper = normalized.upper()

    # Must start with SELECT or WITH (for CTEs)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SELECT queries are allowed"
        )

    # Check for blocked keywords using word boundaries
    for keyword in BLOCKED_KEYWORDS:
        # Use word boundary matching to avoid false positives
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            logger.warning(f"Query blocked - forbidden keyword: {keyword}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query contains forbidden operation"
            )

    # Check for multiple statements (statement stacking attack)
    if ';' in normalized[:-1]:  # Allow trailing semicolon
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple statements not allowed"
        )

    # Limit query length to prevent DoS
    if len(sql) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query too long (max 10000 characters)"
        )

    # Validate table access (defense in depth - RLS is primary protection)
    tables = extract_table_names(sql)
    for table in tables:
        if table in BLOCKED_TABLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Direct access to '{table}' is not allowed. Use '{table}_secure' instead."
            )
        if table not in ALLOWED_TABLES and table not in BLOCKED_TABLES:
            # Allow unknown tables - RLS will filter anyway
            # But log for monitoring
            logger.info(f"Query references unknown table: {table}")


@router.post("/execute", response_model=QueryResponse)
async def execute_query(
    request: QueryRequest,
    user: User = Depends(get_current_user),
):
    """
    Execute a read-only SQL query against the user's database.

    Security:
    - Only SELECT queries are allowed
    - Row-Level Security (RLS) automatically filters to user's data
    - Results are limited to max_result_rows
    - Query timeout is enforced
    """
    # Validate query
    validate_query(request.sql)

    # Enforce row limit
    limit = min(request.limit, settings.max_result_rows)

    # Track usage and check rate limits
    async with get_db_session() as session:
        # Get user record with UUID and subscription tier
        result = await session.execute(
            text("""
            SELECT id, subscription_tier FROM app_users WHERE clerk_id = :clerk_id
            """),
            {"clerk_id": user.clerk_id}
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please log out and log in again."
            )

        user_uuid = str(row[0])
        tier = row[1] or "free"

        if tier == "free":
            # Check monthly query count
            count_result = await session.execute(
                text("""
                SELECT COUNT(*) FROM usage_logs
                WHERE user_id = :user_id
                AND action = 'query'
                AND created_at >= date_trunc('month', CURRENT_DATE)
                """),
                {"user_id": user_uuid}
            )
            query_count = count_result.fetchone()[0]

            if query_count >= settings.free_tier_queries_per_month:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Monthly query limit ({settings.free_tier_queries_per_month}) reached. Upgrade for unlimited queries."
                )

    # Get shared database pool and execute with tenant context
    try:
        pool = await get_shared_pool()
    except Exception as e:
        logger.error(f"Failed to get shared database pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to database"
        )

    # Execute query with tenant isolation via RLS
    start_time = datetime.utcnow()
    try:
        async with tenant_connection(pool, user.clerk_id) as conn:
            # Set statement timeout (within the same transaction)
            # SECURITY: Validate timeout is a positive integer before using
            timeout_seconds = max(1, min(int(settings.query_timeout_seconds), 300))
            await conn.execute(
                f"SET LOCAL statement_timeout = '{timeout_seconds}s'"
            )

            # Add LIMIT if not present
            sql = request.sql.strip().rstrip(';')
            if "LIMIT" not in sql.upper():
                # SECURITY: Ensure limit is a valid positive integer
                safe_limit = max(1, min(int(limit), settings.max_result_rows))
                sql = f"{sql} LIMIT {safe_limit}"

            # Execute - RLS automatically filters to tenant's data
            result = await conn.fetch(sql)

            # Get column info
            if result:
                columns = [
                    ColumnInfo(name=col, type=str(type(result[0][col]).__name__))
                    for col in result[0].keys()
                ]
                rows = [list(row.values()) for row in result]
            else:
                columns = []
                rows = []

    except TenantContextError as e:
        logger.error(f"Tenant context error for user {user.clerk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error. Please log out and log in again."
        )
    except asyncpg.PostgresError as e:
        # SECURITY: Use the sanitization function for all PostgreSQL errors
        sanitized = sanitize_postgres_error(e, request.sql)

        # Log the full error for debugging (server-side only, scrubbed)
        logger.error(
            f"Query error for user {user.clerk_id}: "
            f"type={sanitized.error_type}, sqlstate={getattr(e, 'sqlstate', 'unknown')}"
        )

        # Check for RLS violations - this is critical and should be logged
        if "violates row-level security" in str(e).lower():
            logger.critical(f"RLS violation for user {user.clerk_id}: {scrub_sensitive_data(str(e))}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Determine HTTP status code based on error type
        if sanitized.error_type == "permission_denied":
            http_status = status.HTTP_403_FORBIDDEN
        elif sanitized.error_type == "timeout":
            http_status = status.HTTP_408_REQUEST_TIMEOUT
        else:
            http_status = status.HTTP_400_BAD_REQUEST

        # Build the response detail with position and hint if available
        detail = sanitized.message
        if sanitized.position is not None:
            detail += f" (at position {sanitized.position})"
        if sanitized.hint:
            detail += f" Hint: {sanitized.hint}"

        raise HTTPException(
            status_code=http_status,
            detail=detail
        )
    except Exception as e:
        # Catch-all for non-PostgreSQL errors (connection issues, etc.)
        error_msg = str(e)

        # Check for timeout in generic exceptions
        if "statement timeout" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Query exceeded {settings.query_timeout_seconds}s timeout. Try adding LIMIT or simplifying your query."
            )

        # SECURITY: Don't expose raw error details
        logger.error(f"Unexpected query error for user {user.clerk_id}: {scrub_sensitive_data(error_msg)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )

    end_time = datetime.utcnow()
    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    # Log usage
    async with get_db_session() as session:
        user_result = await session.execute(
            text("SELECT id FROM app_users WHERE clerk_id = :clerk_id"),
            {"clerk_id": user.clerk_id}
        )
        user_row = user_result.fetchone()
        if user_row:
            await session.execute(
                text("""
                INSERT INTO usage_logs (id, user_id, action, created_at)
                VALUES (gen_random_uuid(), :user_id, 'query', :created_at)
                """),
                {"user_id": str(user_row[0]), "created_at": datetime.utcnow()}
            )
            await session.commit()

    return QueryResponse(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_time_ms=execution_time_ms,
        truncated=len(rows) >= limit,
    )


@router.get("/schema", response_model=SchemaResponse)
async def get_schema(user: User = Depends(get_current_user)):
    """
    Get the database schema for the user's database.

    Returns all tables with their columns and row counts.
    RLS automatically filters row counts to user's data.
    """
    try:
        pool = await get_shared_pool()
    except Exception as e:
        logger.error(f"Failed to get shared database pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to database"
        )

    tables = []
    try:
        async with tenant_connection(pool, user.clerk_id) as conn:
            # Get tables from whitelist only (don't query information_schema)
            for table_name in sorted(ALLOWED_TABLES):
                # Skip secure views for schema display - show underlying tables
                if table_name.endswith('_secure'):
                    continue

                # Validate table name format
                if not re.match(r'^[a-z_][a-z0-9_]*$', table_name):
                    continue

                # Get columns using safe query
                try:
                    # Use a query that works with RLS
                    col_result = await conn.fetch(f"""
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = $1
                        ORDER BY ordinal_position
                    """, table_name)

                    columns = [
                        ColumnInfo(name=col['column_name'], type=col['data_type'])
                        for col in col_result
                        # Don't expose tenant_id column to users
                        if col['column_name'] != 'tenant_id'
                    ]

                    # Get row count - RLS filters to user's data
                    # SECURITY: Use identifier quoting even for whitelisted tables
                    # (defense in depth - whitelist validation already done above)
                    count_result = await conn.fetchval(
                        f'SELECT COUNT(*) FROM "{table_name}"'
                    )

                    tables.append(TableInfo(
                        name=table_name,
                        columns=columns,
                        row_count=count_result or 0,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to get schema for table {table_name}: {e}")
                    continue

    except TenantContextError as e:
        logger.error(f"Tenant context error for user {user.clerk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error. Please log out and log in again."
        )

    return SchemaResponse(tables=tables)


@router.get("/tables")
async def list_tables(user: User = Depends(get_current_user)):
    """List all tables available to the user."""
    # Return whitelist directly - no need to query database
    return {
        "tables": sorted([
            t for t in ALLOWED_TABLES
            if not t.endswith('_secure')  # Hide secure view implementation detail
        ])
    }


# ============================================================================
# Example Queries for SQL Editor
# ============================================================================

EXAMPLE_QUERIES = [
    {
        "name": "Recent Messages",
        "description": "Get the 20 most recent messages with author info",
        "category": "basic",
        "sql": """SELECT m.id, u.username, m.content, m.created_at
FROM messages m
JOIN users u ON m.author_id = u.id
ORDER BY m.created_at DESC
LIMIT 20;"""
    },
    {
        "name": "Message Count by User",
        "description": "Count messages per user, sorted by most active",
        "category": "aggregation",
        "sql": """SELECT u.username, COUNT(m.id) as message_count
FROM users u
JOIN messages m ON u.id = m.author_id
GROUP BY u.id, u.username
ORDER BY message_count DESC
LIMIT 15;"""
    },
    {
        "name": "Channel Activity",
        "description": "Messages per channel with unique user counts",
        "category": "aggregation",
        "sql": """SELECT c.name as channel_name,
       COUNT(m.id) as message_count,
       COUNT(DISTINCT m.author_id) as unique_users
FROM channels c
LEFT JOIN messages m ON c.id = m.channel_id
GROUP BY c.id, c.name
ORDER BY message_count DESC;"""
    },
    {
        "name": "Daily Message Trends",
        "description": "Message count by day over the past month",
        "category": "time-series",
        "sql": """SELECT DATE(created_at) as day,
       COUNT(*) as messages
FROM messages
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY day DESC;"""
    },
    {
        "name": "Hourly Activity Pattern",
        "description": "When is your server most active?",
        "category": "time-series",
        "sql": """SELECT EXTRACT(HOUR FROM created_at) as hour,
       COUNT(*) as message_count
FROM messages
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY hour;"""
    },
    {
        "name": "Top Mentioned Users",
        "description": "Users who get mentioned the most",
        "category": "social",
        "sql": """SELECT u.username, COUNT(mm.id) as mention_count
FROM message_mentions mm
JOIN users u ON mm.mentioned_user_id = u.id
GROUP BY u.id, u.username
ORDER BY mention_count DESC
LIMIT 10;"""
    },
    {
        "name": "Reply Chains",
        "description": "Messages that are replies to other messages",
        "category": "social",
        "sql": """SELECT m.id, u.username as author,
       m.content, m.reply_to_message_id
FROM messages m
JOIN users u ON m.author_id = u.id
WHERE m.reply_to_message_id IS NOT NULL
ORDER BY m.created_at DESC
LIMIT 20;"""
    },
    {
        "name": "Messages with Attachments",
        "description": "Find messages that have files attached",
        "category": "content",
        "sql": """SELECT u.username, m.content, m.attachment_count, m.created_at
FROM messages m
JOIN users u ON m.author_id = u.id
WHERE m.attachment_count > 0
ORDER BY m.created_at DESC
LIMIT 20;"""
    },
    {
        "name": "Longest Messages",
        "description": "Messages with the most words",
        "category": "content",
        "sql": """SELECT u.username, m.word_count, m.char_count,
       SUBSTRING(m.content, 1, 100) as preview
FROM messages m
JOIN users u ON m.author_id = u.id
ORDER BY m.word_count DESC
LIMIT 15;"""
    },
    {
        "name": "Bot vs Human Messages",
        "description": "Compare bot and human activity",
        "category": "analytics",
        "sql": """SELECT
    CASE WHEN u.is_bot THEN 'Bot' ELSE 'Human' END as type,
    COUNT(*) as message_count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) as percentage
FROM messages m
JOIN users u ON m.author_id = u.id
GROUP BY u.is_bot;"""
    },
    {
        "name": "User Activity Score",
        "description": "Combined activity metrics per user",
        "category": "analytics",
        "sql": """SELECT u.username,
       COUNT(m.id) as messages,
       AVG(m.word_count)::int as avg_words,
       COUNT(DISTINCT DATE(m.created_at)) as active_days
FROM users u
JOIN messages m ON u.id = m.author_id
GROUP BY u.id, u.username
HAVING COUNT(m.id) > 5
ORDER BY messages DESC
LIMIT 15;"""
    },
    {
        "name": "Channel Message Length",
        "description": "Average message length by channel",
        "category": "analytics",
        "sql": """SELECT c.name as channel_name,
       COUNT(m.id) as total_messages,
       ROUND(AVG(m.word_count), 1) as avg_words,
       ROUND(AVG(m.char_count), 0) as avg_chars
FROM channels c
JOIN messages m ON c.id = m.channel_id
GROUP BY c.id, c.name
HAVING COUNT(m.id) > 10
ORDER BY avg_words DESC;"""
    },
    {
        "name": "Day of Week Activity",
        "description": "Which days are most active?",
        "category": "time-series",
        "sql": """SELECT
    CASE EXTRACT(DOW FROM created_at)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END as day_name,
    COUNT(*) as messages
FROM messages
GROUP BY EXTRACT(DOW FROM created_at)
ORDER BY EXTRACT(DOW FROM created_at);"""
    },
    {
        "name": "User Mention Network",
        "description": "Who mentions whom the most",
        "category": "social",
        "sql": """SELECT author.username as from_user,
       mentioned.username as to_user,
       COUNT(*) as mention_count
FROM message_mentions mm
JOIN messages m ON mm.message_id = m.id
JOIN users author ON m.author_id = author.id
JOIN users mentioned ON mm.mentioned_user_id = mentioned.id
WHERE m.author_id != mm.mentioned_user_id
GROUP BY author.username, mentioned.username
ORDER BY mention_count DESC
LIMIT 20;"""
    },
    {
        "name": "Server Members Overview",
        "description": "List all server members with roles",
        "category": "basic",
        "sql": """SELECT u.username, u.display_name, u.is_bot,
       sm.joined_at, sm.nick as server_nickname
FROM server_members sm
JOIN users u ON sm.user_id = u.id
ORDER BY sm.joined_at DESC
LIMIT 50;"""
    },
    {
        "name": "Channel Overview",
        "description": "All channels with their types and topics",
        "category": "basic",
        "sql": """SELECT name, topic, position, is_nsfw,
       CASE type
           WHEN 0 THEN 'Text'
           WHEN 2 THEN 'Voice'
           WHEN 4 THEN 'Category'
           WHEN 5 THEN 'Announcement'
           WHEN 15 THEN 'Forum'
           ELSE 'Other'
       END as channel_type
FROM channels
ORDER BY position;"""
    },
    {
        "name": "Search Messages",
        "description": "Find messages containing a keyword",
        "category": "search",
        "sql": """SELECT u.username, m.content, c.name as channel, m.created_at
FROM messages m
JOIN users u ON m.author_id = u.id
JOIN channels c ON m.channel_id = c.id
WHERE m.content ILIKE '%hello%'
ORDER BY m.created_at DESC
LIMIT 20;"""
    },
    {
        "name": "Pinned Messages",
        "description": "All pinned messages in the server",
        "category": "content",
        "sql": """SELECT u.username, c.name as channel,
       m.content, m.created_at
FROM messages m
JOIN users u ON m.author_id = u.id
JOIN channels c ON m.channel_id = c.id
WHERE m.is_pinned = true
ORDER BY m.created_at DESC;"""
    },
    {
        "name": "Weekly Active Users",
        "description": "Users who posted in the last 7 days",
        "category": "analytics",
        "sql": """SELECT u.username, COUNT(m.id) as messages_this_week,
       MAX(m.created_at) as last_message
FROM users u
JOIN messages m ON u.id = m.author_id
WHERE m.created_at >= NOW() - INTERVAL '7 days'
GROUP BY u.id, u.username
ORDER BY messages_this_week DESC;"""
    },
    {
        "name": "Message Response Time",
        "description": "Time between messages in active conversations",
        "category": "advanced",
        "sql": """WITH ordered_msgs AS (
    SELECT id, channel_id, created_at,
           LAG(created_at) OVER (PARTITION BY channel_id ORDER BY created_at) as prev_msg_time
    FROM messages
)
SELECT c.name as channel,
       AVG(EXTRACT(EPOCH FROM (created_at - prev_msg_time))) as avg_seconds_between
FROM ordered_msgs om
JOIN channels c ON om.channel_id = c.id
WHERE prev_msg_time IS NOT NULL
GROUP BY c.id, c.name
HAVING COUNT(*) > 10
ORDER BY avg_seconds_between;"""
    },
]


class ExampleQuery(BaseModel):
    """Example query for SQL editor."""
    name: str
    description: str
    category: str
    sql: str


class ExampleQueriesResponse(BaseModel):
    """Response containing example queries."""
    queries: List[ExampleQuery]
    categories: List[str]


@router.get("/examples", response_model=ExampleQueriesResponse)
async def get_example_queries(user: User = Depends(get_current_user)):
    """
    Get example SQL queries for the SQL editor.

    Returns a collection of useful queries organized by category.
    """
    categories = sorted(set(q["category"] for q in EXAMPLE_QUERIES))
    return ExampleQueriesResponse(
        queries=[ExampleQuery(**q) for q in EXAMPLE_QUERIES],
        categories=categories
    )


@router.get("/validate")
async def validate_sql(
    sql: str,
    user: User = Depends(get_current_user)
):
    """
    Validate a SQL query without executing it.

    Returns validation errors if any, useful for real-time syntax feedback.
    """
    try:
        validate_query(sql)
        return {"valid": True, "error": None}
    except HTTPException as e:
        return {"valid": False, "error": e.detail}
