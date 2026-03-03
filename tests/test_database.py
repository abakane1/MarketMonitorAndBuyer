import pytest
import sqlite3
import json
import os
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.database import init_db, db_get_watchlist, db_add_watchlist_with_name, db_remove_watchlist

@pytest.fixture
def mock_db(tmp_path):
    # Use a temporary directory for the mock database
    db_file = tmp_path / "test_user_data.db"
    
    # Patch the DB_FILE used in utils.database
    with patch("utils.database.DB_FILE", str(db_file)):
        init_db()
        yield str(db_file)

def test_init_db_creates_tables(mock_db):
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    assert "watchlist" in tables
    assert "positions" in tables
    assert "history" in tables
    assert "strategy_execution_logs" in tables

def test_watchlist_operations(mock_db):
    # Test add
    db_add_watchlist_with_name("000001", "平安银行")
    db_add_watchlist_with_name("000002", "万科A")
    
    # Test duplicate add (should return true due to ON CONFLICT REPLACE / IGNORE behavior, or raise no error)
    db_add_watchlist_with_name("000001", "平安银行")
    
    watchlist = db_get_watchlist()
    assert len(watchlist) == 2
    assert "000001" in watchlist
    assert "000002" in watchlist
    
    # Test remove
    db_remove_watchlist("000001")
    watchlist_after = db_get_watchlist()
    assert len(watchlist_after) == 1
    assert "000001" not in watchlist_after
