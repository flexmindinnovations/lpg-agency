# Plan: Phase 8 Customer Management

Implement Customer Management functionality across backend API and frontend Dashboard.

## Key Requirements
- Customer aggregate root (`Customer`, `CustomerAddress`, `KycDocument`) with invariants.
- Secure KYC endpoints with separate `kyc:read` and `kyc:manage` permissions.
- App-layer Fernet symmetric encryption for KYC document references.
- Angular lazy-loaded UI module with selection grids and dialog overlays.
