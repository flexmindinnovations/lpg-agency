// Secondary entry point: the ECharts wrapper only.
//
// Kept out of the main `@lpg/shared/ui` barrel on purpose, the same way as
// `data-grid`: importing ECharts registers its chart types as a side effect,
// so anything that imports it loads the whole library. The widget card
// (`ChartCardComponent`) and the token theme (`ChartThemeService`) have no such
// cost and live in the main barrel, so a page can show its cards at once and
// load the charts into them with `@defer`.
export * from './lib/charts/chart.component';
