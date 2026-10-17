import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url


ROOT = Path(__file__).resolve().parents[1]


def migrate_database(database_url: str) -> Engine:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    return create_engine(database_url)


@pytest.fixture
def postgres_engine() -> Iterator[Engine]:
    database_url = os.environ.get("POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("Set POSTGRES_TEST_URL to a disposable PostgreSQL database")

    base_url = make_url(database_url)
    if base_url.get_backend_name() != "postgresql":
        pytest.fail("POSTGRES_TEST_URL must use PostgreSQL")

    schema_name = f"claim_review_test_{uuid4().hex}"
    admin_engine = create_engine(base_url)
    with admin_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')

    isolated_url = base_url.update_query_dict(
        {"options": f"-csearch_path={schema_name}"}
    )
    engine = migrate_database(isolated_url.render_as_string(hide_password=False))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema_name}" CASCADE')
        admin_engine.dispose()