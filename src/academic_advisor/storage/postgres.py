"""Short-lived PostgreSQL connections and ordered, transactional migrations."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from academic_advisor.config import Settings


class DatabaseError(RuntimeError):
    """Safe to display without exposing connection credentials."""


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings

    @contextmanager
    def connection(self, *, vectors: bool = True) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        try:
            with psycopg.connect(
                self.settings.database_url.get_secret_value(),
                row_factory=dict_row,
                connect_timeout=5,
            ) as connection:
                if vectors:
                    register_vector(connection)
                yield connection
        except psycopg.Error:
            raise DatabaseError(
                "PostgreSQL is unavailable or needs initialization. Start the db service "
                "and check DATABASE_URL; use advisor init-db to initialize it."
            ) from None

    def migrate(self) -> None:
        with self.connection(vectors=False) as connection:
            connection.execute("SELECT pg_advisory_xact_lock(80929949)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)"
            )
            applied = {
                row["name"] for row in connection.execute("SELECT name FROM schema_migrations")
            }
            for path in sorted(self.settings.migration_dir.glob("*.sql")):
                if path.name not in applied:
                    connection.execute(path.read_text())
                    connection.execute(
                        "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
                    )
