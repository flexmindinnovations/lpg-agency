# Security Requirements

## 1. Authentication
- Customer App and Driver App: OTP-based mobile authentication (explicit).
- Agency Dashboard: username/password or equivalent, with JWT-based session tokens (explicit) and refresh token support (explicit in extended instructions, not in original blueprint).
- Password/credential policy (complexity, expiry, lockout after failed attempts) — not specified in blueprint; recommended as standard practice, pending confirmation.

## 2. Authorization
- Role-Based Access Control (RBAC) shall govern all Dashboard functionality (explicit).
- Permission-based UI: users shall only see actions/data they are authorized for, not merely be blocked at the API level (explicit in extended instructions — "Permission-based UI").
- **CONFIRMED role list (D-38, `business/decisions.md`)**: Super Admin, Agency Admin, Manager, Warehouse Staff, Dispatcher, Accountant, Driver, Customer. This supersedes the provisional role list in `business/stakeholders.md` §3.
  - **Note:** the exact permission matrix per role, and whether "Warehouse Staff" and the earlier-referenced "Warehouse Manager" (see D-16, inventory adjustment approval authority) are the same role or a staff/manager tier pair, is a residual, non-blocking design-phase question (see `questions/open-questions.md` notes).
- **Super Admin** (new, D-01) operates above the tenant level to manage tenant onboarding/configuration, consistent with the confirmed multi-tenant architecture (BR-30).

## 3. Data Protection
- PII (customer name, phone, address, KYC documents) shall be encrypted at rest and in transit (explicit: "Encryption" in extended instructions).
- KYC documents specifically require restricted access — likely limited to Admin/KYC-verification roles only, not general staff — **inferred, needs confirmation.**
- Payment data shall never be stored directly by the system where avoidable; integration with a PCI-DSS-compliant payment gateway is required for card transactions (industry-standard practice, not explicit in blueprint but necessary given "Card" is a listed payment method).

## 4. API Security
- All APIs shall be secured (explicit: "Secure APIs").
- Rate limiting shall be applied to prevent abuse (explicit).
- OWASP compliance shall be a baseline requirement (explicit) — specific OWASP Top 10 mitigations (injection, broken auth, sensitive data exposure, etc.) should be addressed at the design/architecture stage, out of scope for this SRS but noted as a binding constraint.

## 5. Audit Logging
- All create/update/delete actions on Customers, Orders, Inventory, Payments, and User accounts shall be logged with actor, timestamp, before/after state (explicit: "Audit Logs"; ties to BR-28).
- Audit logs shall be immutable and retained per a data-retention policy — **retention period not specified in blueprint**, Open Question.

## 6. Mobile App Security
- Driver App: given it handles cash-collection and delivery-proof data, device-level security (e.g., app-level PIN, session timeout) should be considered — **inferred, not explicit.**
- Customer App: OTP flows must be protected against abuse (rate limiting on OTP requests, expiry of OTP codes).

## 7. Multi-Tenant Data Isolation — CONFIRMED (D-01)
- The platform is confirmed multi-tenant from Phase 1. Strict tenant-level data isolation (every entity carries `tenantId`; no cross-tenant query/mutation) is now a **hard, Phase 1 security requirement** (BR-30), not a future consideration.

## 8. Regulatory/Compliance Notes
- GST invoicing data must be retained per statutory record-keeping requirements. Jurisdiction is confirmed as India (D-06).
- KYC data handling must comply with applicable Indian data-protection regulation (e.g., DPDP Act). Given the confirmed jurisdiction, this should now be treated as an active compliance requirement to be detailed with legal counsel during design, rather than an open question.
- Authentication now additionally supports optional **Azure AD / Microsoft Entra ID SSO** for agency staff (D-37), alongside JWT + Refresh Tokens and customer OTP.

## 9. Gaps Explicitly Flagged
- No mention in the blueprint of session timeout policy, password reset flow, multi-factor authentication for admin roles, or incident-response procedures. These are standard enterprise security requirements and should be defined before development begins.
