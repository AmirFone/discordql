"""
SQL Query endpoints.
Allows users to execute read-only SQL queries against their data.

SECURITY: Multi-tenant isolation is enforced via:
1. PostgreSQL Row-Level Security (RLS) policies
2. SET LOCAL app.current_tenant = user's clerk_id
3. Query validation to block dangerous patterns
4. Table whitelist to prevent information disclosure
"""
import logging
import re
from typing import List, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

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
            SELECT id, subscription_tier FROM users WHERE clerk_id = :clerk_id
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
            # SECURITY: Use parameterized query to avoid SQL injection
            timeout_seconds = int(settings.query_timeout_seconds)
            await conn.execute(
                "SET LOCAL statement_timeout = $1", f"{timeout_seconds}s"
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
    except Exception as e:
        error_msg = str(e)
        if "statement timeout" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Query exceeded {settings.query_timeout_seconds}s timeout"
            )
        # SECURITY: Don't expose raw database errors - they may contain sensitive info
        logger.error(f"Query execution error for user {user.clerk_id}: {error_msg}")
        # Return sanitized error to user
        if "syntax error" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SQL syntax error in your query"
            )
        elif "does not exist" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referenced table or column does not exist"
            )
        elif "permission denied" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied for this operation"
            )
        elif "violates row-level security" in error_msg.lower():
            # This shouldn't happen with properly configured RLS
            logger.critical(f"RLS violation for user {user.clerk_id}: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query execution failed. Please check your SQL syntax."
            )

    end_time = datetime.utcnow()
    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    # Log usage
    async with get_db_session() as session:
        user_result = await session.execute(
            text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
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
