# Status: Phase 8 Customer Management

**Current Status**: ✅ COMPLETE

## Progress Summary
- Backend models circular references and TYPE_CHECKING import errors resolved (both `infrastructure/persistence/models/customer.py` and `api/v1/schemas/customer.py` — the latter only surfaced via a real HTTP round-trip, not `mypy`/`ruff`).
- Symmetric field encryption at rest integrated for KYC `doc_reference` (Fernet, `Settings.kyc_encryption_key`) — verified directly against the database (raw column holds ciphertext, not plaintext) and round-tripped through a live registration → submit-KYC → verify-KYC flow in a real browser.
- Distinct `kyc:read` and `kyc:manage` permissions applied to router endpoints, narrower than `customers:read`/`customers:update` (migration `c9a1e6b4f7d3`), with 9 new RBAC-boundary tests (`test_customer_rbac.py`).
- Frontend App Route Hygiene tests passing.
- Custom modals replaced with PrimeNG `<p-dialog>` (focus trap, ESC-to-close, ARIA) — found and fixed a follow-on bug where the error-message banner rendered outside the dialog, invisible behind the modal overlay.
- Correct RFC 7807 duplicate error codes returned (`DUPLICATE_PHONE` and `DUPLICATE_CONSUMER_NUMBER`), verified end-to-end in a real browser.
- **Found and fixed a pre-existing, unrelated bug while verifying**: AG Grid's v36 modular architecture requires explicit `ModuleRegistry.registerModules(...)`, never called anywhere in this codebase — row selection and column filtering have been silent no-ops since AG Grid was first wired in (Phase 4). Registered in `DataGridComponent` (the sole AG Grid consumption point). This is why row selection didn't work in Customer Management's detail panel until fixed here.
- Nx project renamed `feature-customers` → `customer-feature-customers` and selector prefix `lib` → `lpg`, matching every other feature library's convention (`eslint.config.mjs`, `project.json`).
- 447 backend tests passing repo-wide (23 customer-specific), `mypy --strict`/`ruff check`/`ruff format --check`/`import-linter` all clean; frontend `lint`/`test`/`build` clean for `dashboard` and `customer-feature-customers`, no CSS budget warnings.
