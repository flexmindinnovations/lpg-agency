# Status

Branch `feat/admin-app-create-customer`, 2026-10-30, stacked on `feat/admin-app-pricing` (PR #86, which stacks on #85, #84, #83, #82; none merged yet). F1 in progress.

## F1 Create customers
Built on `POST /customers`, `POST /customers/{id}/approve`, `POST /customers/{id}/addresses` and `POST /customers/{id}/kyc/{docId}/verify`; no backend change.
- Customers list has an Add button; New order's customer picker has "Add a new customer". Either opens the Add customer form (type, name, mobile, optional second number and email, GSTIN and contact person for businesses, branch when there are several, and a delivery address with city and PIN code). A new customer starts "Onboarding", which can already book.
- The customer page offers Approve (assigns the next consumer number), Add address, and an Identity documents section where a waiting document can be verified or rejected with a reason. The GSTIN shows under contact details.
- Validation: 10-digit mobile, 6-digit PIN, GSTIN pattern, contact person required for commercial (the backend rule), email shape.
Tried on the emulator against the local backend: Add customer (Sunita Walk-in Test, domestic, Kondhwa branch, Pune address) landed on the new customer's page showing "Not approved yet"; Approve made them Active with consumer number CN-000112. That customer is left in the dev database.
Not tried on the emulator: the New order picker entry, a business customer, Add address, and verifying or rejecting a KYC document (the review sheet and the two API calls are covered by tests; no dev customer has a submitted document). Whether a KYC photo shows depends on the backend returning a fetchable URL.
`CustomerResponse` now carries `gstin`. The customer-type labels moved to a shared file used by Pricing and Add customer.

