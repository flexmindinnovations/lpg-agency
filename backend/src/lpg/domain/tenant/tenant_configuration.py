"""`TenantConfiguration` — one historized config value — and
`TenantConfigurationResolver`, the domain service that picks the value in
effect at a point in time (`01-domain-model.md` §5, BR-31).

Append-only by design: a row is never updated after creation. "Changing" a
config value means creating a new `TenantConfiguration` with a later
`effective_from`, never mutating an existing one — this is what lets a past
transaction stay reproducible against whatever value was actually in effect
when it happened, database-enforced by the migration's own grant (SELECT/
INSERT only, no UPDATE/DELETE).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lpg.domain.common.base import AggregateRoot, InvariantViolation

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

#: The fixed set of config keys this phase recognizes
#: (`03-database-schema.md`: "must match recognized key catalog"). Later
#: phases add their own keys here as they need them — `config_value` is
#: `jsonb` specifically so a new key never needs a schema migration, only
#: this catalog updated.
RECOGNIZED_CONFIG_KEYS = frozenset(
    {"gst_rate_percent", "cancellation_fee_amount", "credit_limit_default"}
)


class TenantConfiguration(AggregateRoot):
    __slots__ = ("_config_key", "_config_value", "_effective_from", "_tenant_id")

    def __init__(
        self,
        config_id: uuid.UUID,
        tenant_id: uuid.UUID,
        config_key: str,
        config_value: Any,
        effective_from: datetime,
        *,
        version: int = 1,
    ) -> None:
        super().__init__(config_id, version=version)
        if config_key not in RECOGNIZED_CONFIG_KEYS:
            msg = f"'{config_key}' is not a recognized tenant configuration key."
            raise InvariantViolation(msg, config_key=config_key)

        self._tenant_id = tenant_id
        self._config_key = config_key
        self._config_value = config_value
        self._effective_from = effective_from

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def config_key(self) -> str:
        return self._config_key

    @property
    def config_value(self) -> Any:
        return self._config_value

    @property
    def effective_from(self) -> datetime:
        return self._effective_from


class TenantConfigurationResolver:
    """Resolves the effective value for a config key at a point in time.

    Pure domain logic, no I/O — the repository loads every entry for the
    key; this just picks the one with the latest `effective_from` that is
    not later than `at`. Framework-free, so it is unit-testable without a
    database.
    """

    @staticmethod
    def resolve(
        entries: Sequence[TenantConfiguration], config_key: str, at: datetime
    ) -> TenantConfiguration | None:
        candidates = [
            entry
            for entry in entries
            if entry.config_key == config_key and entry.effective_from <= at
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda entry: entry.effective_from)
