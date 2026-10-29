# Glossary

| Term | Definition |
|---|---|
| **Agency** | The LPG distributor/dealer operating this platform; the tenant business. |
| **OMC** | Oil Marketing Company (e.g., IOCL, BPCL, HPCL) — supplies filled cylinders to the agency. |
| **Filled Cylinder** | A cylinder containing LPG gas, ready for delivery. |
| **Empty Cylinder** | A cylinder that has been fully or partially consumed and returned by the customer for refilling. |
| **Cylinder Exchange** | The core transaction model: customer surrenders an empty cylinder and receives a filled one in the same visit. |
| **Consumer Number** | Unique identifier assigned to a customer's LPG connection, used for order and subsidy tracking (industry-standard term; referenced implicitly via "Consumer number mapping" in blueprint). |
| **Cylinder Ledger** | Per-customer running record of filled cylinders delivered, empty cylinders returned, and current balance. Described as "the most important module" in the blueprint. |
| **KYC** | Know Your Customer — identity verification process for new/existing customer connections. |
| **Refill Booking** | A customer request to receive a new filled cylinder in exchange for an empty one. |
| **Route** | A planned sequence of delivery stops assigned to a driver/vehicle for a shift. |
| **Vehicle Inventory** | The count of filled and empty cylinders currently loaded on a specific delivery vehicle. |
| **Warehouse Inventory** | The count of filled and empty cylinders held at the agency's physical storage location. |
| **Customer Inventory / Customer Holding** | The count of filled and empty cylinders currently in a specific customer's possession. |
| **Proof of Delivery (POD)** | Evidence captured at delivery time: OTP verification, customer signature, photo, and GPS location. |
| **COD** | Cash on Delivery — payment collected by the driver at the point of delivery. |
| **GST** | Goods and Services Tax — the statutory tax regime applicable to LPG sales invoices in India. |
| **Outstanding Balance** | Amount owed by a customer to the agency that has not yet been collected. |
| **Reconciliation** | The process of matching recorded inventory/financial figures against physical/actual counts to identify discrepancies. |
| **Subsidy** | (Inferred, domain-standard, not explicit in blueprint) A government-subsidized price tier for domestic LPG connections, distinct from market-rate commercial pricing. |
| **Domestic Connection** | (Inferred) A residential/household LPG connection, typically subsidized and subject to cylinder-per-year caps. |
| **Commercial Connection** | (Inferred) A business-use LPG connection (restaurants, hotels), typically non-subsidized, larger cylinder sizes. |
| **Cylinder Tare Weight** | (Domain term, not in blueprint) The empty weight of a cylinder, used to verify correct gas fill weight. |
| **BI** | Business Intelligence — analytics/reporting capability referenced under Phase 2. |
| **eKYC** | Electronic KYC — digital identity verification, referenced under Phase 2. |
| **Geo-fencing** | Location-based virtual boundary used for delivery zone management or fraud prevention, referenced under Phase 2. |
| **RBAC** | Role-Based Access Control — permission model restricting dashboard features by staff role. |
| **JWT** | JSON Web Token — authentication token format specified in the technology stack. |
| **API Gateway** | The single entry point routing requests from all three front-ends to backend services. |
| **SLA** | Service Level Agreement — (inferred) target response/delivery times the agency commits to customers. |
| **NFR** | Non-Functional Requirement. |
| **POS** | Point of Sale — (inferred) potential need for in-agency counter sales, not explicit in blueprint. |

## Indian market wording (user-visible text)

Screens, titles, messages and sample data use the words an Indian LPG agency uses day to day, not international equivalents. Code identifiers, routes and API fields keep their English names (`warehouse_id`, `/admin/warehouses`) so nothing breaks.

| Use | Not | Status |
|---|---|---|
| **Godown** | Warehouse | Applied in the dashboard (2026-10-29). Mobile apps, backend messages and printed documents still to do. |
| ₹, `dd/mm/yyyy`, lakh/crore grouping (`1,23,456`) | `$`, `mm/dd/yyyy`, `123,456` | Dates and ₹ already follow this; number grouping is being checked. |
| Pune, Mumbai, Nashik and other Indian places | Springfield, New York | For placeholders, demo data and screenshots. |

Proposed, awaiting product owner sign-off (each changes a lot of screens): Customer → **Consumer**, Inventory → **Stock**, Invoice → **Cash Memo** (for delivery bills), Driver → **Delivery Staff**.
