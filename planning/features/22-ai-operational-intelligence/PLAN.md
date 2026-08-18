# Phase 22 — AI Operational Intelligence

**Status:** 🔵 NOT STARTED · **Depends on:** Phase 21 (AI Foundation)
**Source:** [`docs/research/feature-gap-analysis.md`](../../../docs/research/feature-gap-analysis.md) §4 (A1–A4, A9, A10, A14)

## Framing

Everything here is **classical ML or operations research — no LLMs.** That is a
deliberate choice, not a limitation. These are numeric prediction and
optimisation problems with abundant labelled history, where a gradient-boosted
model is more accurate, three orders of magnitude cheaper, deterministic enough
to test, and explainable enough to defend to a distributor who disagrees with
it. An LLM would be worse on every one of those axes.

Sequenced by dependency: A1 feeds A2, and both feed A3.

## Slice A — Refill-cycle prediction (A1)

**Problem.** Consumers run out, then demand same-day delivery. That wrecks the
Targeted Delivery Time star rating (Phase 20) and shreds route efficiency.

**Data available today.** Per-consumer order history, delivery dates, cylinder
type, branch, seasonality — all in `orders.order` and `orders.order_line`.

**Approach.** Per-consumer inter-refill interval. A hierarchical Bayesian
interval with shrinkage toward the branch × cylinder-type mean handles the long
tail of sparse customers far better than a per-customer fit — most consumers
have few orders, and an unshrunk estimate on three data points is noise.
Gradient-boosted survival is the upgrade path once volume justifies it.

Emits `refill_due_date` per customer, consumed by the notification engine.

**Guardrail.** Never nudge inside the mandated minimum booking gap. That gap is
**tenant-configurable reference data, not a constant** — research §7.3 records
that the widely-quoted 25/45-day figure rests on news reporting of a temporary
measure, not a retrieved notification.

## Slice B — Demand forecasting for indent planning (A2)

**Problem.** Under-indenting causes stockouts; over-indenting ties up working
capital and licensed godown capacity.

**Approach.** Hierarchical time series, branch × cylinder type, gradient
boosting with calendar and festival regressors, reconciled bottom-up to tenant
level. Indian festival calendars move against the Gregorian calendar and are a
first-class regressor, not noise to smooth away.

Output is a daily indent recommendation compared against the distributor's
off-take norm — advisory, never auto-submitted.

## Slice C — Route optimisation (A3)

**Problem.** Routes are built by hand; drivers backtrack; TDT slips.

**Approach.** Capacitated vehicle routing with time windows via OR-Tools.

The detail that matters: **seed travel times from historical POD GPS traces,
not from map estimates.** The platform already captures GPS at every proof of
delivery, which is a record of how long the trip *actually* took on those
streets with that vehicle — far better than a routing engine's idealised
estimate, and it is data no competitor has.

Re-optimisation publishes to the existing Dispatch Board over the WebSocket
channel already built in Phase 3.

## Slice D — Diversion / pilferage anomaly detection (A4)

**Problem.** Domestic cylinders diverted to commercial use, cylinders marked
delivered but never moved, godown shrinkage.

**Approach.** Three layers, deliberately ordered cheapest-first:

1. **Rule-based tripwires** — consumption above *k*× the peer median for the customer class; POD GPS far from the registered address; repeated deliveries to one geohash. Most real detections come from this layer, and it is fully explainable.
2. **Isolation forest / robust z-scores** on staff-day and route-day feature vectors, for patterns the rules miss.
3. **A rank-ordered case queue** — never an automatic block.

**This is an accusation surface.** A false positive here impugns a named
employee, so the output must be a ranked queue for human review, with the
contributing evidence shown. No auto-suspension, ever.

## Slice E — Credit risk scoring (A9)

Commercial 19 kg credit is where bad debt concentrates, and limits today are
set by intuition. Gradient-boosted classifier on 60/90-day delinquency with
**monotonic constraints** so the direction of each factor is guaranteed sane
and defensible. Outputs a recommended limit band plus reason codes.

Advisory with human override, always. An opaque credit denial is both a
commercial problem and a fairness problem.

## Slice F — Churn prediction (A10) and ETA (A14)

Churn: survival model over refill-interval drift plus service-quality features.
The actionable output is nearly always *service recovery*, not a discount —
consumers port because service slipped, and discounting a service failure
treats the symptom.

ETA: gradient boosting on historical stop-to-stop durations, published to the
customer app over the existing WebSocket channel. Directly reduces "where is my
cylinder" calls.

## Cross-cutting verification

- Backtest on held-out time periods, never random splits — random splits leak the future into training and every model looks excellent
- Baseline comparison is mandatory: a model that cannot beat "same interval as last time" ships nothing
- Fairness review on A9 before rollout
- Every prediction traceable to a model version via `ai.prediction` (Phase 21)
- Tenant isolation verified as `lpg_app`

## Open questions

1. Cold-start for new tenants — branch priors, or hold features back until volume exists?
2. Retraining cadence, and what drift signal triggers it.
