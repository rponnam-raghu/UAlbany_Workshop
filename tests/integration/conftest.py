import os
import shutil
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pydantic import SecretStr

from academic_advisor.config import Settings
from academic_advisor.storage.postgres import Database


@pytest.fixture
def database(request, tmp_path):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests.")
    name = f"advisor_test_{uuid4().hex[:10]}"
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            params = psycopg.conninfo.conninfo_to_dict(url)
            params["dbname"] = name
            settings = Settings(database_url=SecretStr(psycopg.conninfo.make_conninfo(**params)), _env_file=None)
            database = Database(settings)
            if getattr(request, "param", None) == "legacy":
                old_migrations = tmp_path / "migrations"
                old_migrations.mkdir()
                for filename in ("001_documents.sql", "002_knowledge_base.sql"):
                    shutil.copy(settings.migration_dir / filename, old_migrations / filename)
                Database(settings.model_copy(update={"migration_dir": old_migrations})).migrate()
            else:
                database.migrate()
            yield database, settings
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
