import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { createBranchApiV1AdminBranchesPost } from './generated/fn/administration/create-branch-api-v-1-admin-branches-post';
import { listBranchesApiV1AdminBranchesGet } from './generated/fn/administration/list-branches-api-v-1-admin-branches-get';
import { renameBranchApiV1AdminBranchesBranchIdRenamePatch } from './generated/fn/administration/rename-branch-api-v-1-admin-branches-branch-id-rename-patch';
import { setBranchRegionApiV1AdminBranchesBranchIdRegionPatch } from './generated/fn/administration/set-branch-region-api-v-1-admin-branches-branch-id-region-patch';
import type { BranchResponse } from './generated/models/branch-response';

/** Thin wrapper over the generated `/admin/branches` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminBranchService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listBranches(): Observable<BranchResponse[]> {
    return listBranchesApiV1AdminBranchesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  createBranch(name: string, region: string | null = null): Observable<BranchResponse> {
    return createBranchApiV1AdminBranchesPost(this.http, this.config.rootUrl, {
      body: { name, region },
    }).pipe(map((response) => response.body));
  }

  renameBranch(branchId: string, name: string): Observable<void> {
    return renameBranchApiV1AdminBranchesBranchIdRenamePatch(this.http, this.config.rootUrl, {
      branch_id: branchId,
      body: { name },
    }).pipe(map(() => undefined));
  }

  setBranchRegion(branchId: string, region: string | null): Observable<void> {
    return setBranchRegionApiV1AdminBranchesBranchIdRegionPatch(this.http, this.config.rootUrl, {
      branch_id: branchId,
      body: { region },
    }).pipe(map(() => undefined));
  }
}
