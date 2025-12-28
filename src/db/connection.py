"""Database connection management."""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from ..config import DATABASE_URL, TEST_DATABASE_URL


def get_engine(test: bool = False) -> Engine:
    """
    Create a database engine.

    Args:
        test: If True, use test database URL

    Returns:
        SQLAlchemy engine
    """
    url = TEST_DATABASE_URL if test else DATABASE_URL
    return create_engine(url, echo=False, pool_pre_ping=True)


def get_session_factory(engine: Engine) -> sessionmaker:
    """Create a session factory bound to an engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Automatically commits on success, rolls back on error.

    Usage:
        with get_session(engine) as session:
            session.add(obj)
    """
    SessionFactory = get_session_factory(engine)
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database(engine: Engine, schema_path: str = "schema.sql") -> None:
    """
    Initialize database with schema.

    Args:
        engine: SQLAlchemy engine
        schema_path: Path to schema.sql file
    """
    with open(schema_path) as f:
        schema_sql = f.read()

    with engine.connect() as conn:
        # Execute each statement separately
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    conn.execute(statement)
                except Exception as e:
                    # Skip errors for IF NOT EXISTS statements
                    if "already exists" not in str(e):
                        print(f"Warning: {e}")
        conn.commit()
