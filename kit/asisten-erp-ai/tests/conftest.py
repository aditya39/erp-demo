import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asisten import config  # noqa: E402


@pytest.fixture(scope="session")
def butuh_db():
    try:
        psycopg.connect(config.DATABASE_URL, connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.skip("Database belum berjalan (docker compose up -d)")
