// Secondary entry point — `AppShellComponent`/`NavGroup`/`ProfileMenuComponent`
// only, deliberately excluding `DataGridComponent`.
//
// `apps/dashboard/src/app/shell/shell-layout.ts` is eagerly loaded (it's the
// parent shell `component:`, not a lazy route), so anything it imports from
// `@lpg/shared/ui`'s main barrel ends up in the initial bundle — including,
// transitively, `ag-grid-community` via `DataGridComponent`'s co-located
// export, even though `ShellLayout` never uses a grid. Found via a real
// bundle-budget failure (main.js grew from ~640kB to ~1.38MB the moment
// Phase 7's admin pages became the first real `DataGridComponent` consumer —
// before that, tree-shaking correctly proved the whole AG Grid dependency
// graph was unused and dropped it everywhere). Importing from this narrower
// entry point instead keeps AG Grid confined to the lazy-loaded feature
// chunks that actually render a grid. `ProfileMenuComponent` lives here too,
// not its own entry point — today it has exactly one consumer
// (`AppShellComponent`, which renders it in the sidebar footer), so it's
// shell-scoped infrastructure rather than a general-purpose export.
export * from './lib/app-shell/app-shell.component';
export * from './lib/app-shell/nav-item';
export * from './lib/profile-menu/profile-menu.component';
