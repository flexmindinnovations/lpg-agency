import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listNotificationSettingsApiV1NotificationSettingsGet } from './generated/fn/notification-settings/list-notification-settings-api-v-1-notification-settings-get';
import { setNotificationSettingApiV1NotificationSettingsNotificationTypePut } from './generated/fn/notification-settings/set-notification-setting-api-v-1-notification-settings-notification-type-put';
import { resetNotificationSettingApiV1NotificationSettingsNotificationTypeDelete } from './generated/fn/notification-settings/reset-notification-setting-api-v-1-notification-settings-notification-type-delete';
import type { NotificationEventResponse } from './generated/models/notification-event-response';
import type { SetNotificationSettingRequest } from './generated/models/set-notification-setting-request';

/** Which channels each system event uses for this agency (ADR-068). */
@Injectable({ providedIn: 'root' })
export class NotificationSettingsService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  list(): Observable<NotificationEventResponse[]> {
    return listNotificationSettingsApiV1NotificationSettingsGet(
      this.http,
      this.config.rootUrl,
    ).pipe(map((res) => res.body.events));
  }

  save(
    notificationType: string,
    body: SetNotificationSettingRequest,
  ): Observable<NotificationEventResponse> {
    return setNotificationSettingApiV1NotificationSettingsNotificationTypePut(
      this.http,
      this.config.rootUrl,
      { notification_type: notificationType, body },
    ).pipe(map((res) => res.body));
  }

  reset(notificationType: string): Observable<NotificationEventResponse> {
    return resetNotificationSettingApiV1NotificationSettingsNotificationTypeDelete(
      this.http,
      this.config.rootUrl,
      { notification_type: notificationType },
    ).pipe(map((res) => res.body));
  }
}
