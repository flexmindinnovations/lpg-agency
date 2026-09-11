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
    {
        "gst_rate_percent",
        "cancellation_fee_amount",
        "credit_limit_default",
        # Nightly `check_compliance_expiry` cron's lead time (days) — how far
        # ahead of a driver/vehicle compliance document's expiry to notify
        # staff. Falls back to `compliance_jobs.DEFAULT_LEAD_DAYS` (30) when
        # a tenant has never set this.
        "compliance_expiry_lead_days",
        # Weighment (Part 2) — the permissible net-weight shortage, in
        # grams, for a filled cylinder before it's flagged underweight.
        # Falls back to `compliance.use_cases.DEFAULT_WEIGHMENT_TOLERANCE_
        # GRAMS` (150g, Legal Metrology (Packaged Commodities) Rules 2011 —
        # confirm against the tenant's own OMC before go-live).
        "weighment_tolerance_grams",
        # The MDG-required maximum least count (grams) a registered scale
        # may have — informational/tenant-visible mirror of `domain.
        # compliance.scale.MAX_LEAST_COUNT_GRAMS` (10g, MDG 2022 cl.
        # 1.2(ii)(iii)), which is the actual hard-enforced domain invariant.
        # This config key exists so the number is documented and
        # tenant-auditable even though nothing currently reads it back to
        # loosen the invariant — a future MDG edition changing the figure
        # updates the domain constant, not this key.
        "weighment_scale_least_count_max_grams",
        # Tenant opt-in for Weighment Part 3's load-out dispatch gate
        # (`LoadVehicleForRouteUseCase`) — defaults to **off** (any falsy or
        # absent value) so a tenant that hasn't set up scales/weighment yet
        # sees no change to route loading. A tenant sets this to a truthy
        # value only once they've actually adopted weighment.
        "weighment_gate_enabled",
        # TDT (Targeted Delivery Time) star rating (Phase 20 subsystem 2) —
        # `domain.compliance.tdt_rating`'s star-band day-thresholds,
        # version-stamped with the MDG edition they came from:
        # `{"mdg_edition": "MDG-2022", "bands": [{"stars": 5, "max_days": N},
        # ..., {"stars": 1, "max_days": null}]}`. No default in code — a
        # tenant with no entry for this key has no TDT rating computable
        # yet, which is the correct behaviour until the real bands are
        # confirmed against the tenant's own OMC (see PLAN.md's open
        # questions — the MDG edition itself is unresolved).
        "tdt_star_rating_bands",
        # TDT fine schedule — the percentage owed for N consecutive
        # sub-threshold quarters, same version-stamping requirement:
        # `{"mdg_edition": "MDG-2022", "rules": [{"consecutive_low_quarters":
        # N, "fine_percent": "X.XX"}, ...]}`. Kept as its own key, separate
        # from `tdt_star_rating_bands`, because the two are independently
        # revisable — an OMC could update the day-thresholds without
        # touching the fine schedule, matching how `weighment_tolerance_
        # grams` and `weighment_gate_enabled` are already two keys rather
        # than one combined weighment-config blob.
        "tdt_fine_schedule",
        # Cylinder Identity (Phase 20 subsystem 3) — Rule 35(1), Gas
        # Cylinders Rules 2016, defers the actual retest interval to IS
        # 15975, which this codebase has never retrieved. Convenience
        # prefill ONLY: `RecordStatutoryTestUseCase` suggests
        # `tested_at + N months` as the next due date when this key is
        # set. The due date actually persisted is always the caller's own
        # value — never silently computed server-side — so an unset key
        # means "no suggestion offered," not "no due date can be recorded."
        "cylinder_statutory_test_interval_months",
        # AI Model Gateway (Phase 21 substrate, ADR-045) — tenant opt-in for
        # the AI Command Center, same default-off shape as
        # `weighment_gate_enabled`: a tenant that has never set this key
        # sees no change, the gateway is never called.
        "ai_gateway_enabled",
        # Optional per-tenant override of the daily token budget the AI
        # Model Gateway enforces before every call — falls back to
        # `application.ai.use_cases.DEFAULT_AI_DAILY_TOKEN_BUDGET` when a
        # tenant has never set this.
        "ai_daily_token_budget",
        # Zero-click driver auto-assignment (order-to-delivery fulfillment
        # automation) — tenant opt-in, same default-off shape as
        # `weighment_gate_enabled`/`ai_gateway_enabled`: a tenant that has
        # never set this key sees zero behavior change,
        # `auto_assign_driver` always no-ops and the order waits for the
        # existing manual assign flow, exactly as it does today. Checked
        # with `application.common.config.is_truthy_config_value()` — the
        # same jsonb-string-"false" footgun named for `ai_gateway_enabled`
        # applies here too.
        "auto_assignment_enabled",
        # Stale-unassigned-order alert (order-to-delivery fulfillment
        # automation's own survey of other automatable processes) — how
        # many hours an order may sit `confirmed` (unassigned) before
        # branch staff are alerted. Optional per-tenant override; falls
        # back to `infrastructure.jobs.stale_order_jobs.
        # DEFAULT_STALE_HOURS` (4) when unset. A tuning knob, not a kill
        # switch — this alert is a pure read + notify, not an
        # irreversible action, so unlike `auto_assignment_enabled` it has
        # no on/off gate of its own.
        "stale_unassigned_order_hours",
        # Refill-due proactive nudge (AI Operational Intelligence, Horizon
        # 1 Stage 2) — tenant opt-in, same default-off shape as
        # `auto_assignment_enabled`/`ai_gateway_enabled`: a tenant that has
        # never set this sees zero behavior change — `predict_refill_due`
        # still writes today's `ai.prediction` row for every customer (the
        # traceable read model `GET /customers/refill-due` serves), it
        # just never enqueues a `refill_due_customer` notification.
        "refill_nudge_enabled",
        # How many days before a customer's predicted refill date to nudge
        # them. Optional per-tenant override; falls back to
        # `infrastructure.jobs.refill_jobs.DEFAULT_LEAD_DAYS` (3) when unset.
        "refill_nudge_lead_days",
        # Minimum days since a customer's last delivery before this nudge
        # will ever fire — a sanity floor against a short/noisy blended
        # interval estimate, not an enforced order-placement rule elsewhere
        # in this codebase (there isn't one). Optional per-tenant override;
        # falls back to `infrastructure.jobs.refill_jobs.
        # DEFAULT_MIN_GAP_DAYS` (5) when unset.
        "refill_nudge_min_gap_days",
    }
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
