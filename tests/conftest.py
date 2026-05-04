import sqlite3
from pathlib import Path

import pytest

from stonks.models.database import init_db


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    return init_db(tmp_path / "test.db")
