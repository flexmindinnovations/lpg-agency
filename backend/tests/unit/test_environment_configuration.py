"""DEV / UAT / PROD configuration verification (Phase 2, Area A).

Loads the actual committed example files — the templates every developer and
every environment copies from (`cp .env.dev.example .env`, etc.) — and asserts
the resulting ``Settings`` are coherent and, most importantly, that DEV and UAT
can never resolve to the same connection target as PROD. A config typo that
pointed local development at the real Supabase host would be exactly the
"accidentally connect local development to PROD" failure mode this guards
against.

This also doubles as a repo-hygiene check: the PROD template must never carry
a real password, mirroring the guard that already caught two real secrets
committed/staged earlier in this project's history (a Supabase password in
`.env.prod.example`, a PrimeNG licence key in `app.config.ts`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lpg.config.settings import Settings

if TYPE_CHECKING:
    import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal ``KEY=VALUE`` parser for the committed example files.

    Not a general-purpose dotenv parser — these files are hand-authored and
    simple by convention (no quoting, no multiline values), so a full parser
    would be more machinery than the input shape ever needs.
    """
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _settings_from_example(filename: str, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Build ``Settings`` from a committed example file's values.

    Applied via environment variables (what actually happens once a developer
    copies the file to ``.env`` and it is loaded), not by reading the file as
    a dotenv source directly — this keeps the test exercising the same
    precedence rules ``Settings`` uses in production.
    """
    values = _parse_env_file(_BACKEND_ROOT / filename)
    for key, value in values.items():
        if value:
            monkeypatch.setenv(key, value)
        else:
            monkeypatch.delenv(key, raising=False)
    return Settings()


class TestDevConfiguration:
    def test_dev_targets_local_docker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings_from_example(".env.dev.example", monkeypatch)

        assert settings.environment == "dev"
        assert settings.is_local is False
        url = settings.effective_database_url
        assert "localhost" in url
        assert "55432" in url
        assert "lpg_dev" in url
        assert "lpg_app" in url
        assert "supabase" not in url

    def test_dev_migration_url_uses_the_elevated_local_role(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _settings_from_example(".env.dev.example", monkeypatch)

        assert "lpg_admin" in settings.effective_migration_url
        assert "localhost" in settings.effective_migration_url


class TestUatConfiguration:
    def test_uat_targets_a_separate_local_database_and_role(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _settings_from_example(".env.uat.example", monkeypatch)

        assert settings.environment == "uat"
        url = settings.effective_database_url
        assert "localhost" in url
        assert "lpg_uat" in url
        assert "lpg_app_uat" in url
        assert "supabase" not in url

    def test_uat_and_dev_never_resolve_to_the_same_database(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dev = _settings_from_example(".env.dev.example", monkeypatch)
        uat = _settings_from_example(".env.uat.example", monkeypatch)

        assert dev.effective_database_url != uat.effective_database_url
        assert dev.db_user != uat.db_user


class TestProdConfiguration:
    def test_prod_template_carries_no_real_password(self) -> None:
        """Repo-hygiene guard: the committed PROD template must stay a template.

        A real password here would be a live credential leak the moment
        someone reads this file — exactly the class of mistake already found
        and fixed once in this repository's history.
        """
        values = _parse_env_file(_BACKEND_ROOT / ".env.prod.example")

        assert values["LPG_DB_PASSWORD"] == ""

    def test_prod_targets_the_real_supabase_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies the template *shape* resolves correctly once a password is
        supplied — without ever supplying a real one in a test."""
        monkeypatch.setenv("LPG_DB_PASSWORD", "test-only-placeholder")
        settings = _settings_from_example(".env.prod.example", monkeypatch)

        assert settings.environment == "production"
        url = settings.effective_database_url
        assert "supabase.co" in url
        assert "ayqphthelemlnbtnknkp" in url

    def test_prod_never_resolves_to_a_local_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LPG_DB_PASSWORD", "test-only-placeholder")
        settings = _settings_from_example(".env.prod.example", monkeypatch)

        url = settings.effective_database_url
        assert "localhost" not in url
        assert "127.0.0.1" not in url


class TestNoAccidentalCrossEnvironmentTargeting:
    """The specific failure mode Phase 2's instructions call out by name:
    local development must never end up pointed at the production database."""

    def test_dev_and_prod_hosts_are_disjoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dev = _settings_from_example(".env.dev.example", monkeypatch)
        monkeypatch.setenv("LPG_DB_PASSWORD", "test-only-placeholder")
        prod = _settings_from_example(".env.prod.example", monkeypatch)

        assert dev.effective_database_url != prod.effective_database_url
        assert "supabase" not in dev.effective_database_url
        assert "localhost" not in prod.effective_database_url

    def test_uat_and_prod_hosts_are_disjoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        uat = _settings_from_example(".env.uat.example", monkeypatch)
        monkeypatch.setenv("LPG_DB_PASSWORD", "test-only-placeholder")
        prod = _settings_from_example(".env.prod.example", monkeypatch)

        assert uat.effective_database_url != prod.effective_database_url
        assert "supabase" not in uat.effective_database_url
