import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable, map } from 'rxjs';
import {
  ApiConfiguration,
  assignComplaintApiV1ComplaintsComplaintIdAssignPost,
  getComplaintApiV1ComplaintsComplaintIdGet,
  listComplaintsApiV1ComplaintsGet,
  raiseComplaintApiV1ComplaintsPost,
  listComplaintAssigneesApiV1ComplaintsAssigneesGet,
  resolveComplaintApiV1ComplaintsComplaintIdResolvePost,
  type AssignComplaintRequest as GeneratedAssignComplaintRequest,
  type ComplaintAssigneeResponse,
  type ComplaintCategory,
  type ComplaintPriority,
  type ComplaintResponse,
  type ComplaintStatus,
  type RaiseComplaintRequest as GeneratedRaiseComplaintRequest,
  type ResolutionOutcome,
  type ResolveComplaintRequest as GeneratedResolveComplaintRequest,
} from '@lpg/shared/data-access';

// The generated contract (DO-17..DO-20): names, numbers and the safety
// category come from the server instead of hand-kept copies.
export type Complaint = ComplaintResponse;
export type ComplaintAssignee = ComplaintAssigneeResponse;
export type { ComplaintCategory, ComplaintPriority, ResolutionOutcome };

export interface ComplaintListResponse {
  items: Complaint[];
  total: number;
  skip: number;
  limit: number;
}

export type RaiseComplaintRequest = GeneratedRaiseComplaintRequest;
export type AssignComplaintRequest = GeneratedAssignComplaintRequest;
export type ResolveComplaintRequest = GeneratedResolveComplaintRequest;

/**
 * Was a hand-rolled `HttpClient` service with a hardcoded relative
 * `'/api/v1/complaints'` base — unlike every other feature's service, it
 * never resolved against `ApiConfiguration.rootUrl` (`http://localhost:8000`
 * in dev), so every request instead hit the Angular dev server's own origin.
 * GETs silently came back as the SPA's `index.html` (parsed as an empty
 * list, no error surfaced), and POSTs 404'd with the dev server's own
 * "Cannot POST ..." page. The entire feature — list, raise, assign, resolve
 * — was unreachable from the real backend. Now routed through the same
 * generated-client + `ApiConfiguration` pattern every other service uses.
 */
@Injectable({
  providedIn: 'root',
})
export class ComplaintService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listComplaints(
    skip = 0,
    limit = 50,
    status?: ComplaintStatus,
    customer_id?: string,
  ): Observable<ComplaintListResponse> {
    return listComplaintsApiV1ComplaintsGet(this.http, this.config.rootUrl, {
      skip,
      limit,
      status,
      customer_id,
    }).pipe(map((res) => res.body as unknown as ComplaintListResponse));
  }

  /** Staff who can take complaints, with their names (DO-18). */
  listAssignees(): Observable<ComplaintAssignee[]> {
    return listComplaintAssigneesApiV1ComplaintsAssigneesGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  getComplaint(id: string): Observable<Complaint> {
    return getComplaintApiV1ComplaintsComplaintIdGet(this.http, this.config.rootUrl, {
      complaint_id: id,
    }).pipe(map((res) => res.body as unknown as Complaint));
  }

  raiseComplaint(request: RaiseComplaintRequest): Observable<{ id: string }> {
    return raiseComplaintApiV1ComplaintsPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body as { id: string }));
  }

  assignComplaint(id: string, request: AssignComplaintRequest): Observable<void> {
    return assignComplaintApiV1ComplaintsComplaintIdAssignPost(this.http, this.config.rootUrl, {
      complaint_id: id,
      body: request,
    }).pipe(map(() => undefined));
  }

  resolveComplaint(id: string, request: ResolveComplaintRequest): Observable<void> {
    return resolveComplaintApiV1ComplaintsComplaintIdResolvePost(this.http, this.config.rootUrl, {
      complaint_id: id,
      body: request,
    }).pipe(map(() => undefined));
  }
}
