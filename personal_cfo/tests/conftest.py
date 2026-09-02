"""Shared pytest fixtures.

Every test gets a fresh, throwaway SQLite database (never the real
data/cfo.db) and a controllable "current tenant" so multi-tenancy
behavior can be exercised without going through Streamlit's auth layer.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from cfo import db as db_module


@pytest.fixture
def base_env():
    """A clean environment for subprocess-based tests (test_dbconn_encryption.py)
    -- inherits PATH etc. but never leaks a real DB_ENCRYPTION_KEY from the
    outer environment into what's supposed to be a controlled test case."""
    env = dict(os.environ)
    env.pop("DB_ENCRYPTION_KEY", None)
    return env


@pytest.fixture
def monkeypatch_env_without_key(base_env):
    return base_env


@pytest.fixture
def uninitialized_tenant(tmp_path, monkeypatch):
    """Like `tenant`, but does NOT call init_db() -- for tests that need to
    write their own pre-migration schema into DB_PATH first and control
    exactly when init_db()'s migration runs."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "cfo.db")
    state = {"id": "local"}
    monkeypatch.setattr(db_module, "current_user_id", lambda: state["id"])

    class Tenant:
        def as_(self, tenant_id: str) -> None:
            state["id"] = tenant_id

    return Tenant()


@pytest.fixture
def tenant(uninitialized_tenant):
    """Points cfo.db at a fresh temp file (already on the current schema)
    and lets the test control which tenant is "current" via
    tenant.as_("some-id"). Starts as 'local'."""
    db_module.init_db()
    return uninitialized_tenant


@pytest.fixture
def db(tenant):
    """The cfo.db module itself, already pointed at a fresh temp database."""
    return db_module
