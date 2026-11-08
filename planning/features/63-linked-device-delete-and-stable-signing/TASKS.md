# Tasks: linked device delete and stable test signing

- [ ] 1. Domain: `DeviceDeleted` event and `LinkedDevice.delete()`; unit tests
- [ ] 2. Migration: grant `DELETE` on `platform.linked_device` to the app role
- [ ] 3. Repository `delete`; `DeleteDeviceUseCase` (tenant check, audit `device.deleted`); unit tests
- [ ] 4. `DELETE /admin/license/devices/{id}` (204), event handler (clear cache, end sessions, tell the app); API integration tests including another agency's phone
- [ ] 5. Regenerate the OpenAPI spec and the dashboard API client
- [ ] 6. Dashboard: Delete row action with confirmation; tests
- [ ] 7. Internal-test keystore, Gradle signing config for the Admin, Driver and Customer apps, CI workflow uses it; document in `mobile/RELEASE.md`
- [ ] 8. ADR-073; STATUS and `MODULE_STATUS.md` updated
