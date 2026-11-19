// Secondary entry point — `DataGridComponent` and its column/cell types.
//
// Kept out of the main `@lpg/shared/ui` barrel on purpose: the grid pulls in
// AG Grid (~1.2 MB), and anything that imports from the main barrel ends up
// loading it, grid or not (the dashboard home was loading it for a few stat
// cards). Pages that render a grid import from here, so AG Grid stays in the
// lazy chunks that use it. Same pattern as `@lpg/shared/ui/app-shell`.
export * from './lib/data-grid/data-grid.component';
