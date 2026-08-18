# Phase 21 — AI Foundation

**Status:** 🔵 NOT STARTED · **Depends on:** Phase 20 (Regulatory & MDG Compliance)
**Source:** [`docs/research/feature-gap-analysis.md`](../../../docs/research/feature-gap-analysis.md) §4

## Why this phase exists separately

Nothing in this phase is a user-facing feature. It is the substrate every AI
feature in Phases 22 and 23 sits on, and it is separated for one reason: the
failure modes of AI features are *not* the failure modes of CRUD features, and
they cannot be retrofitted.

A wrong `POST /orders` returns a 400. A wrong forecast returns a confident
number. A wrong text-to-SQL query returns *another tenant's rows* unless
something outside the model prevents it. The controls that make that safe —
tenant isolation at the session, evaluation before rollout, cost ceilings,
PII redaction, and a kill switch — belong to the platform, not to each feature.

Building them once, first, is also what keeps model choice reversible.

## Scope

### 1. Model gateway (`infrastructure/ai/`)

A single outbound seam for every model call, following the existing port/adapter
convention — `application/ai/ports.py` defines the Protocol, infrastructure
implements it. No feature module imports a vendor SDK directly.

Responsibilities: provider routing and fallback, per-tenant and per-feature
budget ceilings, token accounting written to the audit log, timeout and retry,
prompt/response capture for evaluation, and structured-output enforcement.

**All calls are tenant-attributed.** The gateway takes the tenant from
`RequestTenantContext`, never from a caller-supplied argument — the same
mistake `TenantContext`-as-Protocol produced in Phase 13 is available here in a
more expensive form.

### 2. Feature store (`ai` schema)

Point-in-time-correct feature retrieval for training and inference. Materialised
from existing tables; **no new source of truth.** Tenant-scoped with the same
`ENABLE` + `FORCE ROW LEVEL SECURITY` and null-safe predicate as every other
tenant table (`08-security-architecture.md` §3.1) — verified by
`scripts/verify_env_parity.sql` like everything else.

Training-serving skew is the defect to design against: the same code path must
produce features for both, or the model silently degrades in production while
scoring well offline.

### 3. Evaluation harness

A model reaches production only through a recorded evaluation. Golden datasets
per feature, offline metrics appropriate to the task (not accuracy on
imbalanced problems), and for LLM features an adversarial suite covering prompt
injection, cross-tenant leakage attempts and refusal behaviour.

This is the direct analogue of `MODULE_STATUS.md`: a claim that a model works
is not evidence that it works.

### 4. Inference serving

Batch scoring via the existing ARQ worker (`bulk_cancel_orders` is the
precedent). Online scoring behind the model gateway with a cache. Predictions
are written to `ai.prediction` with model version, input hash, and timestamp so
any number shown to a user can be traced to the model that produced it.

### 5. Guardrails and governance

- **Every AI output is advisory by default.** Nothing in Phases 22–23 may take an irreversible action — no auto-cancel, no auto-credit-denial, no auto-complaint-closure.
- **Feature-flagged per tenant**, reusing the existing `tenant.feature_flag_override` system, so a misbehaving model is switched off without a deploy.
- **PII redaction before egress**, with DPDP retention constraints applied to prompt/response capture (research §7.7 — the per-rule commencement schedule is not settled; build to configurable retention).
- **Kill switch** at the gateway, per feature and per tenant.
- New permission codes: `ai:read`, `ai:configure`, `ai:override`.

## Deliberately out of scope

Model *training* infrastructure. Phase 22 models are small enough to train in a
scheduled job; a training platform is not justified by the data volume.

## Verification

- `verify_env_parity.sql` returns zero defects for the new `ai` schema
- A cross-tenant retrieval attempt against the feature store returns zero rows, tested **as `lpg_app`** (as superuser it will falsely pass — §3.1)
- Budget ceiling breach degrades gracefully rather than erroring the request
- Kill switch verified live: flag off → feature disappears, no deploy
- Import-linter: `application/ai` imports domain only; no vendor SDK outside `infrastructure/ai`

## Open questions

1. Model hosting — hosted API vs self-hosted for Indic language work. Bears on DPDP data residency; not decided.
2. Whether the feature store needs its own retention policy distinct from the operational tables.
