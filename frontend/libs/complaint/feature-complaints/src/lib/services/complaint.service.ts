import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

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

@Injectable({
  providedIn: 'root',
})
export class ComplaintService {
  private http = inject(HttpClient);
  private apiUrl = '/api/v1/complaints';

  listComplaints(
    skip = 0,
    limit = 50,
    status?: string,
    customer_id?: string
  ): Observable<ComplaintListResponse> {
    let params = new HttpParams()
      .set('skip', skip.toString())
      .set('limit', limit.toString());

    if (status) {
      params = params.set('status', status);
    }
    if (customer_id) {
      params = params.set('customer_id', customer_id);
    }

    return this.http.get<ComplaintListResponse>(this.apiUrl, { params });
  }

  getComplaint(id: string): Observable<Complaint> {
    return this.http.get<Complaint>(`${this.apiUrl}/${id}`);
  }

  raiseComplaint(request: RaiseComplaintRequest): Observable<{ id: string }> {
    return this.http.post<{ id: string }>(this.apiUrl, request);
  }

  assignComplaint(id: string, request: AssignComplaintRequest): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/${id}/assign`, request);
  }

  resolveComplaint(id: string, request: ResolveComplaintRequest): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/${id}/resolve`, request);
  }
}
