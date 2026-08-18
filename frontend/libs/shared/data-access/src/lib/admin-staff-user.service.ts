import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { deactivateStaffUserApiV1AdminUsersUserIdDeactivatePatch } from './generated/fn/administration/deactivate-staff-user-api-v-1-admin-users-user-id-deactivate-patch';
import { inviteStaffUserApiV1AdminUsersPost } from './generated/fn/administration/invite-staff-user-api-v-1-admin-users-post';
import { listStaffUsersApiV1AdminUsersGet } from './generated/fn/administration/list-staff-users-api-v-1-admin-users-get';
import { reassignRoleApiV1AdminUsersUserIdRolePatch } from './generated/fn/administration/reassign-role-api-v-1-admin-users-user-id-role-patch';
import { getUserPermissionsApiV1AdminUsersUserIdPermissionsGet } from './generated/fn/administration/get-user-permissions-api-v-1-admin-users-user-id-permissions-get';
import { updateUserPermissionsApiV1AdminUsersUserIdPermissionsPut } from './generated/fn/administration/update-user-permissions-api-v-1-admin-users-user-id-permissions-put';
import { listPermissionsApiV1AdminPermissionsGet } from './generated/fn/administration/list-permissions-api-v-1-admin-permissions-get';
import type { StaffUserResponse } from './generated/models/staff-user-response';

/** Thin wrapper over the generated `/admin/users` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminStaffUserService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listStaffUsers(): Observable<StaffUserResponse[]> {
    return listStaffUsersApiV1AdminUsersGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  inviteStaffUser(
    email: string,
    role: string,
    branchId: string | null = null,
  ): Observable<StaffUserResponse> {
    return inviteStaffUserApiV1AdminUsersPost(this.http, this.config.rootUrl, {
      body: { email, role, branch_id: branchId },
    }).pipe(map((response) => response.body));
  }

  deactivateStaffUser(userId: string): Observable<void> {
    return deactivateStaffUserApiV1AdminUsersUserIdDeactivatePatch(this.http, this.config.rootUrl, {
      user_id: userId,
    }).pipe(map(() => undefined));
  }

  reassignRole(userId: string, newRole: string): Observable<void> {
    return reassignRoleApiV1AdminUsersUserIdRolePatch(this.http, this.config.rootUrl, {
      user_id: userId,
      body: { new_role: newRole },
    }).pipe(map(() => undefined));
  }

  listPermissions(): Observable<string[]> {
    return listPermissionsApiV1AdminPermissionsGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  getUserPermissions(userId: string): Observable<string[]> {
    return getUserPermissionsApiV1AdminUsersUserIdPermissionsGet(this.http, this.config.rootUrl, {
      user_id: userId,
    }).pipe(map((response) => response.body));
  }

  updateUserPermissions(userId: string, permissionCodes: string[]): Observable<void> {
    return updateUserPermissionsApiV1AdminUsersUserIdPermissionsPut(this.http, this.config.rootUrl, {
      user_id: userId,
      body: { permission_codes: permissionCodes },
    }).pipe(map(() => undefined));
  }
}
