# Business Overview

## 1. Purpose of This Document

This document establishes the business context for the LPG Agency Management Platform. It is the entry point for the full Software Requirements Specification (SRS) located under `/docs`. It is written for stakeholders who need to understand *why* the system exists before diving into modules, workflows, and detailed requirements.

## 2. Business Domain

The domain is **LPG (Liquefied Petroleum Gas) cylinder distribution**, operated by a franchised **LPG Agency** (also called a "distributor") acting on behalf of an Oil Marketing Company (OMC) such as Indian Oil Corporation (IOCL), Bharat Petroleum (BPCL), or Hindustan Petroleum (HPCL), or operating as an independent regional LPG dealer.

An LPG agency's core commercial activity is a **cylinder exchange economy**: a customer does not "buy" a cylinder outright on every order — they exchange an empty cylinder for a filled one and pay for the gas (plus applicable deposits, delivery charges, and taxes). This exchange-based model is the central business rule that shapes almost every module in the system (see `business-rules.md` and `workflows/cylinder-ledger.md`).

## 3. Problem Being Solved

Per the source blueprint, most LPG agencies today operate with disconnected systems or manual/paper-based processes, resulting in:

- Poor visibility into filled vs. empty cylinder stock (at warehouse, vehicle, and customer level)
- Delivery tracking issues (no real-time status, no proof of delivery)
- Inventory mismatches (stock counts drift from physical reality over time)
- Delayed accounting and billing (manual reconciliation, delayed GST reporting)
- Customer service challenges (no self-service booking, no complaint tracking)
- Lack of real-time reporting for owners/managers to make decisions

## 4. Proposed Solution Summary

A unified digital platform with three connected front-ends sharing one backend and one source of truth:

1. **Customer Mobile App** — booking, tracking, payments, complaints
2. **Delivery Driver Mobile App** — assigned deliveries, live inventory tracking, delivery confirmation, payment collection
3. **Agency Web Dashboard** — customer management, order management, inventory management, delivery management, accounting, reporting, administration

All three surfaces read and write against a single **Customer Cylinder Ledger** and a single **Inventory Ledger**, so that the number of filled/empty cylinders at the warehouse, on each vehicle, and with each customer is always reconcilable and auditable.

## 5. Business Objectives

| # | Objective | Why It Matters |
|---|---|---|
| 1 | Digitize the full cylinder lifecycle (booking → delivery → reconciliation) | Eliminates paper registers and manual stock books |
| 2 | Provide real-time, per-customer cylinder balance | Prevents disputes, theft, and over/under-delivery |
| 3 | Provide real-time inventory visibility at warehouse, vehicle, and customer level | Enables accurate replenishment and loss prevention |
| 4 | Automate accounting, invoicing, and GST-compliant billing | Reduces manual errors, speeds up statutory reporting |
| 5 | Give agency owners real-time operational KPIs | Enables data-driven decisions (staffing, routing, stock ordering) |
| 6 | Improve customer experience (self-service booking, tracking, complaints) | Increases retention, reduces call-center load |
| 7 | Improve delivery accountability (OTP, signature, photo, GPS proof) | Reduces disputes and fraud, protects drivers and agency alike |
| 8 | Lay groundwork for AI/analytics-driven growth (Phase 2) | Demand forecasting, route optimization, predictive inventory |

## 6. Business Value / Expected Outcomes

- Reduction in inventory shrinkage/loss through auditable cylinder movement tracking.
- Faster cash collection cycle through digital payment collection at the doorstep.
- Reduced customer complaints related to "missing" cylinder balances.
- Improved driver productivity through route/delivery assignment visibility.
- Statutory (GST) reporting readiness at all times instead of month-end scrambles.
- A platform capable of onboarding **multiple agencies/distributors** in the future (multi-tenant potential — see Open Questions).

## 7. Regulatory Context (Domain-Specific — Not Explicit in Blueprint)

LPG distribution in most jurisdictions (notably India, given references to IOCL/BPCL/HPCL) is a **regulated business**. The following regulatory considerations are *inferred* from domain knowledge and are **not explicitly covered in the source blueprint** — they must be validated with the business:

- Cylinder possession limits per household/connection (regulatory cap, varies by region).
- Subsidy vs. non-subsidy pricing (in India, LPG subsidies are common — this affects invoicing/accounting logic significantly).
- Safety inspection and expiry-date tracking for cylinders (statutory requirement in many regions).
- KYC / Aadhaar-linked or equivalent identity verification for new connections.
- License/permit tracking for the agency itself (explosives license, trade license, etc.).
- GST invoicing rules specific to LPG (HSN codes, tax slabs) — mentioned only generically as "GST reports" in the blueprint.

These are flagged in `assumptions.md` and `questions/open-questions.md`.

## 8. Relationship to Source Blueprint

This SRS is derived from, and expands upon, the attached `LPG_Agency_Management_System_Blueprint.pdf`. Where the blueprint is explicit, this SRS reflects it faithfully. Where the blueprint is silent, gaps are explicitly flagged rather than silently assumed — per the governing instruction for this documentation effort.

## 9. Document Map

- `stakeholders.md` — actors and their goals
- `glossary.md` — domain terminology
- `business-rules.md` — invariant rules governing the domain
- `assumptions.md` — assumptions made while producing this SRS (now cross-referenced against confirmed decisions)
- `decisions.md` — **confirmed stakeholder decisions resolving all original open questions; the current source of truth wherever it conflicts with an earlier assumption**
- `modules/*.md` — one document per business module, including the newly added `complaint-management.md`
- `workflows/*.md` — key end-to-end business workflows
- `requirements/*.md` — functional and non-functional requirements
- `questions/open-questions.md` — status tracker; all originally open items are now Resolved (see `decisions.md`)

## 10. Update Note

This SRS was originally produced with a large number of explicitly flagged gaps and open questions, per the governing instruction to state missing information rather than assume it. The business has since supplied confirmed decisions for every one of those items (see `business/decisions.md`). Documents throughout `/docs` have been updated to reflect these decisions, with each change traceable back to its decision ID (D-01 through D-42). A small number of narrower, design-phase follow-up questions were surfaced during this update (see `questions/open-questions.md` "Notes on Resolution Quality") — these are minor and do not block proceeding to system design.
