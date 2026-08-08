# 02 — User Personas

Each persona maps to a confirmed platform role (`docs/data/05-reference-data.md` §8, D-38).

## 1. Agency Owner / Agency Admin — "Vikram"
**Role:** `agency_admin`
**Goals:** See revenue, outstanding payments, and stock health at a glance; trust that staff are following process; grow the business without needing to be in the office.
**Responsibilities:** Tenant configuration (GST rates, cylinder caps, credit limits), staff account management, final approval authority (refunds, large reconciliation variances, post-dispatch cancellations).
**Pain Points (today, pre-platform):** No real-time visibility into cylinder stock; disputes with customers over "how many cylinders do I have"; manual reconciliation of cash from drivers takes hours.
**Daily Tasks:** Open Dashboard KPI view once or twice a day; approve pending refunds/reconciliation variances; occasionally review staff performance reports.
**Accessibility Needs:** Needs summarized views (KPI cards, charts) more than dense tables — low tolerance for friction.
**Technology Comfort Level:** Medium. Comfortable with smartphones and basic web apps; not a power user of enterprise software. Needs the Dashboard's summary views to require zero training.

## 2. Manager — "Sunita"
**Role:** `manager`
**Goals:** Keep daily operations running smoothly; resolve escalations before they reach the Owner; approve time-sensitive actions quickly.
**Responsibilities:** Approve post-dispatch cancellations (D-19), approve credit notes (D-17), oversee Dispatcher and Warehouse Staff, handle escalated complaints.
**Pain Points:** Approval requests arrive by phone call or in-person interruption today; no single queue of "things waiting on me."
**Daily Tasks:** Check an approval queue multiple times a day; review complaint escalations; spot-check driver performance.
**Accessibility Needs:** Needs fast, low-friction approval flows (approve/reject inline from a queue, not a multi-step form).
**Technology Comfort Level:** Medium-high. Uses the Dashboard for a meaningful fraction of the workday.

## 3. Dispatcher — "Ramesh"
**Role:** `dispatcher`
**Goals:** Get every day's orders onto efficient routes with the right driver/vehicle, with minimal manual reshuffling.
**Responsibilities:** Route planning, driver/vehicle assignment, monitoring live delivery progress, handling failed-delivery reschedules.
**Pain Points:** Route planning today is done on paper or a spreadsheet; no visibility into which orders are at risk of running out of vehicle stock until a driver calls in.
**Daily Tasks:** Plan routes each morning (potentially dozens of orders across multiple drivers); reassign failed deliveries throughout the day; monitor a live delivery-status board.
**Accessibility Needs:** The platform's highest-density, highest-frequency power-user screen — needs full keyboard operability, bulk selection, drag-and-drop with a keyboard-accessible fallback.
**Technology Comfort Level:** High for this specific workflow even if generally moderate with other software.

## 4. Warehouse Staff — "Deepak"
**Role:** `warehouse_staff`
**Goals:** Keep an accurate count of filled/empty/damaged stock; load vehicles correctly each morning; reconcile at day's end without discrepancies.
**Responsibilities:** Record GRN receipts, load vehicles, perform inventory adjustments (with approval where required), participate in shift reconciliation.
**Pain Points:** Manual stock registers drift from reality; no easy way to flag a damaged cylinder mid-shift.
**Daily Tasks:** Morning vehicle loading (repetitive, time-pressured); occasional adjustment entries; end-of-day reconciliation.
**Accessibility Needs:** Likely uses a shared warehouse terminal or tablet, sometimes with gloves on — larger touch targets and minimal typing (numeric steppers over free-text fields) matter more here than anywhere else in the Dashboard.
**Technology Comfort Level:** Low-to-medium. Likely the least tech-comfortable Dashboard user.

## 5. Accountant — "Priya"
**Role:** `accountant`
**Goals:** Accurate, GST-compliant invoicing; fast reconciliation of driver cash collections; clean outstanding-balance tracking.
**Responsibilities:** Review invoices/payments, process refund requests (request-level, approval by Manager/Admin), generate GST and financial reports, reconcile cash handovers.
**Pain Points:** Manual GST calculation errors; chasing outstanding balances without a clear aging view.
**Daily Tasks:** Review the day's invoices and payments; process any refund requests; run periodic reports.
**Accessibility Needs:** Heavy Data Grid and report user — needs strong filtering/export, and printing fidelity is directly her professional output.
**Technology Comfort Level:** Medium-high, especially with spreadsheet-like tools.

## 6. Driver — "Suresh"
**Role:** `driver`
**Goals:** Get through the day's deliveries efficiently, get paid correctly, avoid disputes over cylinder counts or cash.
**Responsibilities:** Execute deliveries, capture Proof of Delivery, collect payment, participate in reconciliation.
**Pain Points:** Poor connectivity in some delivery areas; today's paper-based delivery slips get lost or are illegible.
**Daily Tasks:** View assigned route each morning; navigate to each stop; confirm delivery (OTP, signature, photo, GPS — BR-08/BR-23); collect payment; return for reconciliation.
**Accessibility Needs:** Uses the Driver App outdoors, in bright sunlight, often one-handed while also holding a cylinder — very large touch targets, high contrast, minimal required typing, and the app must work fully **offline** (D-24).
**Technology Comfort Level:** Variable, often the platform's least tech-experienced user group.

## 7. Customer — "Meera"
**Role:** `customer`
**Goals:** Book a refill quickly, know when it's arriving, pay conveniently, get help if something's wrong.
**Responsibilities:** N/A (consumer role).
**Pain Points:** Today, booking means a phone call during business hours; no visibility into when the cylinder will actually arrive; no easy way to check her own cylinder balance history.
**Daily Tasks (occasional, not daily):** Book a refill roughly monthly; occasionally track a delivery in progress; occasionally raise a complaint.
**Accessibility Needs:** Broad range of ages and technical comfort — needs the largest accessibility safety margin of the three apps (larger default text, forgiving touch targets, multi-language support per D-27).
**Technology Comfort Level:** Highly variable, skews lower on average than the Dashboard's staff users.

## Cross-Persona Notes
- **Warehouse Staff and Driver** share the platform's highest accessibility/simplicity bar due to environmental constraints (gloves, sunlight, one-handed use, low connectivity) — design decisions here should default toward the more constrained persona, not the average user.
- **Dispatcher and Accountant** are the platform's power users of the Data Grid and keyboard shortcuts — optimizing for their repeated-daily-use speed has the highest ROI of any UX investment in the Dashboard.
- **Agency Owner and Manager** need summarized, approval-oriented views far more than raw data tables — their screens should default to "what needs my attention" over "here is everything."
