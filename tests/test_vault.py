"""Vault facade and configuration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from memoryvault import Vault, __version__
from memoryvault.config import VaultConfig


def test_vault_open_persists_database(tmp_path: Path, docs_dir: Path):
    db = tmp_path / "vault.db"
    with Vault.open(db) as vault:
        vault.index(docs_dir)
        assert vault.repo.count() == 8
    assert db.exists()

    with Vault.open(db) as reopened:
        assert reopened.repo.count() == 8


def test_vault_in_memory_is_isolated(docs_dir: Path):
    a, b = Vault.in_memory(), Vault.in_memory()
    a.index(docs_dir)
    assert a.repo.count() == 8
    assert b.repo.count() == 0
    a.close()
    b.close()


def test_vault_stats_facade(indexed_vault):
    stats = indexed_vault.stats()
    assert stats["documents"] == 8
    assert stats["events"] >= 8


def test_version():
    assert __version__ == "1.0.0"


def test_config_defaults():
    cfg = VaultConfig().resolve()
    assert cfg.max_file_size > 0
    assert "md" in cfg.extensions
    assert "node_modules" in cfg.excluded_dirs
    assert 0 < cfg.simhash_threshold < 64


def test_config_memoryvault_home_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORYVAULT_HOME", str(tmp_path / "custom"))
    from memoryvault.config import _default_home

    assert _default_home() == tmp_path / "custom"
    assert VaultConfig().db_path == tmp_path / "custom" / "memoryvault.db"


def test_config_api_env_vars(monkeypatch):
    # Containers rely on these to bind 0.0.0.0 — a loopback-only default
    # makes `docker run -p` unreachable (connection reset).
    monkeypatch.setenv("MEMORYVAULT_API_HOST", "0.0.0.0")
    monkeypatch.setenv("MEMORYVAULT_API_PORT", "9000")
    cfg = VaultConfig()
    assert cfg.api_host == "0.0.0.0"
    assert cfg.api_port == 9000


def test_config_api_env_defaults(monkeypatch):
    monkeypatch.delenv("MEMORYVAULT_API_HOST", raising=False)
    monkeypatch.delenv("MEMORYVAULT_API_PORT", raising=False)
    cfg = VaultConfig()
    assert cfg.api_host == "127.0.0.1"
    assert cfg.api_port == 8000


def test_config_api_env_invalid_port_falls_back(monkeypatch):
    monkeypatch.setenv("MEMORYVAULT_API_PORT", "not-a-number")
    assert VaultConfig().api_port == 8000


def test_simhash_threshold_flows_into_vault(docs_dir: Path):
    vault = Vault.in_memory(simhash_threshold=3)
    assert vault.dedup.threshold == 3
    vault.index(docs_dir)
    assert vault.repo.count() == 8
    vault.close()
