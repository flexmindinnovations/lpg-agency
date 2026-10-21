import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { changeMyPasswordApiV1AuthMePasswordPost } from './generated/fn/authentication/change-my-password-api-v-1-auth-me-password-post';
import { getMyProfileApiV1AuthMeProfileGet } from './generated/fn/authentication/get-my-profile-api-v-1-auth-me-profile-get';
import { updateMyProfileApiV1AuthMeProfilePatch } from './generated/fn/authentication/update-my-profile-api-v-1-auth-me-profile-patch';
import type { MyProfileResponse } from './generated/models/my-profile-response';
import type { UpdateMyProfileRequest } from './generated/models/update-my-profile-request';

/** Thin wrapper over the generated `/auth/me/profile` and `/auth/me/password`
 * client functions — the signed-in user's own account (DA-30). */
@Injectable({ providedIn: 'root' })
export class MyProfileService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  getProfile(): Observable<MyProfileResponse> {
    return getMyProfileApiV1AuthMeProfileGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  updateProfile(changes: UpdateMyProfileRequest): Observable<MyProfileResponse> {
    return updateMyProfileApiV1AuthMeProfilePatch(this.http, this.config.rootUrl, {
      body: changes,
    }).pipe(map((response) => response.body));
  }

  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return changeMyPasswordApiV1AuthMePasswordPost(this.http, this.config.rootUrl, {
      body: { current_password: currentPassword, new_password: newPassword },
    }).pipe(map(() => undefined));
  }
}
