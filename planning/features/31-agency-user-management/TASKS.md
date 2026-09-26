# Tasks: Agency User Management

- [x] 1. Setting `setup_link_ttl_seconds` (24 h); Create agency uses it
- [x] 2. Migration `e7d1a3c5f9b2`: `identity.auth_invalidate_password_reset_tokens`; `PasswordResetTokenRepository.invalidate_unused_for_user`
- [x] 3. Application: `PlatformAuditTrail` port; `ListAgencyUsers`, `AddAgencyAdmin`, `IssueSetupLink` (+ shared `issue_setup_token`); 14 unit tests
- [x] 4. Infrastructure: `SqlAlchemyPlatformAuditTrail`
- [x] 5. API: three routes + schemas; OpenAPI exported; client regenerated
- [x] 6. Integration tests (real PostgreSQL): 7 pass - add admin (+permissions, 24 h link), users scoped to the agency, duplicate email, old link killed / new usable, other-agency user -> 404, closed agency -> 409, audit attributed to the agency without the token
- [x] 7. Frontend: service methods, Users section, generic setup-link drawer; 23 page tests
- [x] 8. Live verification: 15-check HTTP walkthrough against the local stack; UI exercised in a real browser
- [x] 9. Docs: ADR-049, MODULE_STATUS row 27, DEPLOY.md recovery procedure
- [ ] 10. Deploy to production and verify there (a push to `main` deploys automatically)

## Deferred

- Revoking a user's refresh tokens when a reset link is used (predates this feature)
- Email delivery of links (needs a provider)
- An authenticated change-password endpoint
- Deactivating / removing an agency user from the Platform Console
- Light-theme and narrow-width review of the Users block
