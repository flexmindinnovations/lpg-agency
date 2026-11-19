// Secondary entry point — the chart wrapper (Apache ECharts), the widget card
// and the token-driven chart theme.
//
// Kept out of the main `@lpg/shared/ui` barrel on purpose, the same way as
// `data-grid`: ECharts is a large dependency, and anything that imports from
// the main barrel would load it on every page. Dashboard widgets import from
// here and are `@defer`red, so it only loads where a chart is drawn.
export * from './lib/charts/chart.component';
export * from './lib/charts/chart-card.component';
export * from './lib/charts/chart-theme.service';
