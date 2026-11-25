"""Tests never touch the owner's real run folders (~/.nerdit-social)."""
import pytest


@pytest.fixture(autouse=True)
def private_social_home(tmp_path, monkeypatch):
    monkeypatch.setenv("NERDIT_SOCIAL_HOME", str(tmp_path / "social-home"))
