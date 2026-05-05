import sqlite3
from pathlib import Path

import pytest

from stonks.models.database import init_db
from stonks.services import stock_data


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    return init_db(tmp_path / "test.db")


@pytest.fixture(autouse=True)
def clear_stock_data_caches():
    stock_data._info_cache.clear()
    stock_data._history_cache.clear()
    yield
    stock_data._info_cache.clear()
    stock_data._history_cache.clear()
