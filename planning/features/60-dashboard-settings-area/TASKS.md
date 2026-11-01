# Tasks: Dashboard Settings Area

- [x] 1. Show the agency code on the Profile page (PR #5, `9bff24c`)
- [x] 2. `SettingsShell` + `settings-sections.ts`; `/settings/*` child routes with per-section guards
- [x] 3. Read-only Agency section (`GET /admin/tenant`); agency code moved off Profile
- [x] 4. Sidebar: four admin entries replaced by one Settings item; command palette lists each section
- [x] 5. Redirect `/profile` and the four `/admin/*` URLs; update the license guard exemption, `LicenseRequired` link and the TDT cross-links
- [x] 6. Remove "My Profile" from the user menu; update its unit and e2e specs
- [x] 7. Flat cards inside Settings (`--card-border` / `--card-shadow` hooks)
- [x] 8. Unit tests, lint, production build; browser check against a stub API (PR #6, `98e530a`)
- [x] 9. Deploy to the droplet (run 38900287128, images `8976567`)
- [x] 10. ADR-070, MODULE_STATUS row, this folder
- [x] 11. Open Configuration, TDT Rating, Feature Flags, License and Linked Devices with real data on the deployed site (all render; see STATUS)
- [ ] 12. Run `apps/dashboard-e2e/src/profile-menu.spec.ts` (needs a signed-in session; updated but not run)

## Deferred

- A blocked-license tenant on `/settings/license` still sees the other Settings sections in the nav; they bounce back to `/license-required`. Hiding them needs the nav to read the license status.
- Retire the legacy redirects once no bookmarks or links use the old URLs.
- Editable agency details, if the product owner wants them.
