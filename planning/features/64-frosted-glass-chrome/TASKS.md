# Tasks - 64 Frosted glass chrome

- [x] Web: `--glass-*` tokens in all four theme selectors
- [x] Web: `.glass` utility, overlay rules (dialog, drawer, toast), fallbacks (`@supports`, reduced transparency, print)
- [x] Web: header and sidebar use `.glass`; grain tile preloaded in `index.html`
- [x] Mobile: `LpgGlassTokens`, `LpgGlassPolicy`, `LpgGlassChrome`
- [x] Mobile: navigation bar and sheets use `LpgGlassChrome`; tests and goldens updated
- [ ] Measure on devices: Chrome/Safari scroll traces, low-end Android raster time, Flutter DevTools (cannot be done in the cloud)
- [ ] Mobile: frosted toasts and scrolled header
- [ ] Mobile: frame-time monitor that turns `LpgGlassPolicy.blur` off when slow
