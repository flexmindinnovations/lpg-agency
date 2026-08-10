export * from './lib/problem-details';
export * from './lib/correlation.interceptor';
export * from './lib/auth-token.store';
export * from './lib/auth.service';
export * from './lib/auth.interceptor';
export * from './lib/auth.guard';
export * from './lib/permission.guard';

// Phase 7 (Administration) — thin wrappers over the generated
// `/admin/*` client functions, same pattern as auth.service.ts.
export * from './lib/admin-tenant.service';
export * from './lib/admin-branch.service';
export * from './lib/admin-warehouse.service';
export * from './lib/admin-cylinder-type.service';
export * from './lib/admin-tenant-configuration.service';
export * from './lib/admin-price-list.service';
export * from './lib/admin-feature-flag.service';
export * from './lib/admin-staff-user.service';
export * from './lib/admin-audit-log.service';

// ng-openapi-gen output (ADR-032) — regenerated, never hand-edited.
export * from './lib/generated/api-configuration';
export * from './lib/generated/api';
export * from './lib/generated/models';
export * from './lib/generated/functions';
