"""Sign-in keys: none committed, and the generator writes a working pair."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import TYPE_CHECKING

import jwt
import pytest
from dotenv import dotenv_values

from lpg.config.settings import Settings

if TYPE_CHECKING:
    from types import ModuleType

_BACKEND = Path(__file__).resolve().parents[2]
_REPOSITORY = _BACKEND.parent

#: Every tracked file that has held, or is a natural home for, a sign-in key.
_COMMITTED_CONFIG = [
    _REPOSITORY / ".claude" / "backend-dev.bat",
    _REPOSITORY / ".env.example",
    _BACKEND / ".env.example",
    _BACKEND / ".env.dev.example",
    _BACKEND / ".env.uat.example",
    _BACKEND / ".env.prod.example",
]

_PEM_HEADER = re.compile(r"-----BEGIN [A-Z ]*KEY-----")
_KEY_ASSIGNMENT = re.compile(r"(?m)^\s*(?:set\s+)?LPG_JWT_(?:PRIVATE|PUBLIC)_KEY=[ \t]*\S")


def _generator() -> ModuleType:
    path = _BACKEND / "scripts" / "generate_jwt_keys.py"
    spec = importlib.util.spec_from_file_location("generate_jwt_keys", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _settings_from(path: Path) -> Settings:
    values = dotenv_values(path)
    return Settings(
        environment="dev",
        jwt_private_key=values["LPG_JWT_PRIVATE_KEY"],
        jwt_public_key=values["LPG_JWT_PUBLIC_KEY"],
    )


def _assert_pair_signs_and_verifies(settings: Settings) -> None:
    assert settings.jwt_private_key is not None
    assert settings.jwt_public_key is not None
    token = jwt.encode(
        {"sub": "check"}, settings.jwt_private_key.get_secret_value(), algorithm="RS256"
    )
    assert jwt.decode(token, settings.jwt_public_key, algorithms=["RS256"])["sub"] == "check"


class TestNoCommittedKeys:
    @pytest.mark.parametrize("path", _COMMITTED_CONFIG, ids=lambda path: path.name)
    def test_committed_config_carries_no_key(self, path: Path) -> None:
        if not path.exists():
            pytest.skip(f"{path.name} is not part of this copy")
        text = path.read_text(encoding="utf-8")

        # Booleans, so that a failure never prints the key into a log.
        has_pem = _PEM_HEADER.search(text) is not None
        has_assignment = _KEY_ASSIGNMENT.search(text) is not None
        assert not has_pem, f"{path.name} contains a PEM key"
        assert not has_assignment, f"{path.name} sets a sign-in key"

    def test_blank_key_settings_count_as_unset(self) -> None:
        settings = Settings(environment="dev", jwt_private_key="", jwt_public_key="  ")

        assert settings.jwt_private_key is None
        assert settings.jwt_public_key is None


class TestGenerator:
    def test_replaces_a_multi_line_pair_and_keeps_other_settings(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_bytes(
            b"# a comment\r\n"
            b"LPG_ENVIRONMENT=dev\r\n"
            b'LPG_JWT_PRIVATE_KEY="old line one\r\nold line two\r\n"\r\n'
            b'LPG_JWT_PUBLIC_KEY="old public one\r\nold public two\r\n"\r\n'
            b"LPG_DB_NAME=lpg_dev\r\n"
        )

        fingerprint = _generator().write_new_keys(env)

        text = env.read_text(encoding="utf-8")
        assert "old line" not in text
        assert "old public" not in text
        assert "# a comment" in text
        values = dotenv_values(env)
        assert values["LPG_ENVIRONMENT"] == "dev"
        assert values["LPG_DB_NAME"] == "lpg_dev"
        assert len(fingerprint) == 64
        _assert_pair_signs_and_verifies(_settings_from(env))

    def test_fills_the_blank_lines_of_an_example_file(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_bytes((_BACKEND / ".env.dev.example").read_bytes())

        _generator().write_new_keys(env)

        assert env.read_text(encoding="utf-8").count("LPG_JWT_PRIVATE_KEY=") == 1
        _assert_pair_signs_and_verifies(_settings_from(env))

    def test_appends_when_the_file_has_no_key_lines(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("LPG_ENVIRONMENT=dev", encoding="utf-8")

        _generator().write_new_keys(env)

        assert dotenv_values(env)["LPG_ENVIRONMENT"] == "dev"
        _assert_pair_signs_and_verifies(_settings_from(env))

    def test_each_run_makes_a_different_pair(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("", encoding="utf-8")
        generator = _generator()

        assert generator.write_new_keys(env) != generator.write_new_keys(env)

    def test_reports_a_missing_file(self, tmp_path: Path) -> None:
        assert _generator().main([str(tmp_path / "absent.env")]) == 1
