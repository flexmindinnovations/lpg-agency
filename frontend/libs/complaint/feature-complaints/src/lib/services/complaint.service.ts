import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable, map } from 'rxjs';
import {
  ApiConfiguration,
  assignComplaintApiV1ComplaintsComplaintIdAssignPost,
  getComplaintApiV1ComplaintsComplaintIdGet,
  listComplaintsApiV1ComplaintsGet,
  raiseComplaintApiV1ComplaintsPost,
  resolveComplaintApiV1ComplaintsComplaintIdResolvePost,
} from '@lpg/shared/data-access';

export interface ComplaintAssignment {
  id: string;
  assigned_to: string;
  assigned_at: string;
  created_at: string;
  created_by?: string;
}

export interface ComplaintResolution {
  id: string;
  outcome: 'Resolved' | 'Compensated' | 'Rejected';
  resolution_notes: string;
  resolved_by: string;
  resolved_at: string;
  created_at: string;
}

export interface Complaint {
  id: string;
  complaint_number?: string;
  customer_id: string;
  order_id?: string;
  category: string;
  priority: string;
  status: 'Open' | 'Assigned' | 'InProgress' | 'Resolved' | 'Rejected' | 'Closed';
  description: string;
  sla_due_at?: string;
  created_at: string;
  updated_at: string;
  created_by?: string;
  updated_by?: string;
  assignments: ComplaintAssignment[];
  resolution?: ComplaintResolution;
}

export interface ComplaintListResponse {
  items: Complaint[];
  total: number;
  skip: number;
  limit: number;
}

export interface RaiseComplaintRequest {
  customer_id: string;
  category: string;
  priority: string;
  description: string;
  order_id?: string;
}

export interface AssignComplaintRequest {
  assigned_to: string;
}

export interface ResolveComplaintRequest {
  outcome: 'Resolved' | 'Compensated' | 'Rejected';
  resolution_notes: string;
}

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
    status?: string,
    customer_id?: string
  ): Observable<ComplaintListResponse> {
    return listComplaintsApiV1ComplaintsGet(this.http, this.config.rootUrl, {
      skip,
      limit,
      status,
      customer_id,
    }).pipe(map((res) => res.body as unknown as ComplaintListResponse));
  }

  getComplaint(id: string): Observable<Complaint> {
    return getComplaintApiV1ComplaintsComplaintIdGet(this.http, this.config.rootUrl, {
      complaint_id: id,
    }).pipe(map((res) => res.body as unknown as Complaint));
  }

  raiseComplaint(request: RaiseComplaintRequest): Observable<{ id: string }> {
    return raiseComplaintApiV1ComplaintsPost(this.http, this.config.rootUrl, {
      body: request as never,
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
      body: request as never,
    }).pipe(map(() => undefined));
  }
}
