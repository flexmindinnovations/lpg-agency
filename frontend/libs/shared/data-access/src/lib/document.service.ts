import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { uploadDocumentAttachmentApiV1DocumentsAttachmentsPost } from './generated/fn/documents/upload-document-attachment-api-v-1-documents-attachments-post';
import { recognizeDocumentApiV1DocumentsRecognizePost } from './generated/fn/documents/recognize-document-api-v-1-documents-recognize-post';
import { listDriverDocumentsApiV1DriversDriverIdDocumentsGet } from './generated/fn/delivery/list-driver-documents-api-v-1-drivers-driver-id-documents-get';
import { addDriverDocumentApiV1DriversDriverIdDocumentsPost } from './generated/fn/delivery/add-driver-document-api-v-1-drivers-driver-id-documents-post';
import { listVehicleDocumentsApiV1VehiclesVehicleIdDocumentsGet } from './generated/fn/delivery/list-vehicle-documents-api-v-1-vehicles-vehicle-id-documents-get';
import { addVehicleDocumentApiV1VehiclesVehicleIdDocumentsPost } from './generated/fn/delivery/add-vehicle-document-api-v-1-vehicles-vehicle-id-documents-post';
import { listWarehouseDocumentsApiV1WarehousesWarehouseIdDocumentsGet } from './generated/fn/delivery/list-warehouse-documents-api-v-1-warehouses-warehouse-id-documents-get';
import { addWarehouseDocumentApiV1WarehousesWarehouseIdDocumentsPost } from './generated/fn/delivery/add-warehouse-document-api-v-1-warehouses-warehouse-id-documents-post';
import { listTenantDocumentsApiV1TenantDocumentsGet } from './generated/fn/delivery/list-tenant-documents-api-v-1-tenant-documents-get';
import { addTenantDocumentApiV1TenantDocumentsPost } from './generated/fn/delivery/add-tenant-document-api-v-1-tenant-documents-post';
import { replaceComplianceDocumentApiV1ComplianceDocumentsDocumentIdPut } from './generated/fn/delivery/replace-compliance-document-api-v-1-compliance-documents-document-id-put';
import { verifyComplianceDocumentApiV1ComplianceDocumentsDocumentIdVerifyPost } from './generated/fn/delivery/verify-compliance-document-api-v-1-compliance-documents-document-id-verify-post';
import { listComplianceDocumentsApiV1ComplianceDocumentsGet } from './generated/fn/delivery/list-compliance-documents-api-v-1-compliance-documents-get';
import type { AddComplianceDocumentRequest } from './generated/models/add-compliance-document-request';
import type { ComplianceDocumentListResponse } from './generated/models/compliance-document-list-response';
import type { ComplianceDocumentResponse } from './generated/models/compliance-document-response';
import type { DocumentAttachmentResponse } from './generated/models/document-attachment-response';
import type { RecognizeComplianceDocumentResponse } from './generated/models/recognize-compliance-document-response';
import type { ReplaceComplianceDocumentRequest } from './generated/models/replace-compliance-document-request';
import type { VerifyComplianceDocumentRequest } from './generated/models/verify-compliance-document-request';

export type DocumentKind = 'driving_licence' | 'vehicle_rc';
export type ComplianceOwnerType = 'driver' | 'vehicle' | 'warehouse' | 'tenant';

export interface ComplianceDocumentListFilter {
  owner_type?: ComplianceOwnerType;
  status?: string;
  expiry?: 'expiring' | 'expired';
  skip?: number;
  limit?: number;
}

/**
 * Thin wrapper over the generated `/documents` + compliance-document client
 * functions — same pattern as `CustomerService`. Feeds `<lpg-document-upload>`
 * (`uploadAttachment` / `recognize`) and the driver/vehicle compliance panels.
 */
@Injectable({ providedIn: 'root' })
export class DocumentService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  /** Stage a document image; returns the blob ref to attach it with later. */
  uploadAttachment(file: File): Observable<DocumentAttachmentResponse> {
    return uploadDocumentAttachmentApiV1DocumentsAttachmentsPost(this.http, this.config.rootUrl, {
      body: { file },
    }).pipe(map((res) => res.body));
  }

  /** Server-side OCR "second pass" for a driving licence / RC image. */
  recognize(
    blobRef: string,
    docKind: DocumentKind,
  ): Observable<RecognizeComplianceDocumentResponse> {
    return recognizeDocumentApiV1DocumentsRecognizePost(this.http, this.config.rootUrl, {
      body: { blob_ref: blobRef, doc_kind: docKind },
    }).pipe(map((res) => res.body));
  }

  listDriverDocuments(driverId: string): Observable<ComplianceDocumentListResponse> {
    return listDriverDocumentsApiV1DriversDriverIdDocumentsGet(this.http, this.config.rootUrl, {
      driver_id: driverId,
    }).pipe(map((res) => res.body));
  }

  addDriverDocument(
    driverId: string,
    body: AddComplianceDocumentRequest,
  ): Observable<ComplianceDocumentResponse> {
    return addDriverDocumentApiV1DriversDriverIdDocumentsPost(this.http, this.config.rootUrl, {
      driver_id: driverId,
      body,
    }).pipe(map((res) => res.body));
  }

  listVehicleDocuments(vehicleId: string): Observable<ComplianceDocumentListResponse> {
    return listVehicleDocumentsApiV1VehiclesVehicleIdDocumentsGet(this.http, this.config.rootUrl, {
      vehicle_id: vehicleId,
    }).pipe(map((res) => res.body));
  }

  addVehicleDocument(
    vehicleId: string,
    body: AddComplianceDocumentRequest,
  ): Observable<ComplianceDocumentResponse> {
    return addVehicleDocumentApiV1VehiclesVehicleIdDocumentsPost(this.http, this.config.rootUrl, {
      vehicle_id: vehicleId,
      body,
    }).pipe(map((res) => res.body));
  }

  /** Compliance Calendar (ADR-044) — PESO Form F per warehouse. */
  listWarehouseDocuments(warehouseId: string): Observable<ComplianceDocumentListResponse> {
    return listWarehouseDocumentsApiV1WarehousesWarehouseIdDocumentsGet(
      this.http,
      this.config.rootUrl,
      { warehouse_id: warehouseId },
    ).pipe(map((res) => res.body));
  }

  addWarehouseDocument(
    warehouseId: string,
    body: AddComplianceDocumentRequest,
  ): Observable<ComplianceDocumentResponse> {
    return addWarehouseDocumentApiV1WarehousesWarehouseIdDocumentsPost(
      this.http,
      this.config.rootUrl,
      { warehouse_id: warehouseId, body },
    ).pipe(map((res) => res.body));
  }

  /** Compliance Calendar (ADR-044) — the tenant's own insurance policy. No
   * owner id: the backend always scopes this to the caller's own tenant. */
  listTenantDocuments(): Observable<ComplianceDocumentListResponse> {
    return listTenantDocumentsApiV1TenantDocumentsGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  addTenantDocument(body: AddComplianceDocumentRequest): Observable<ComplianceDocumentResponse> {
    return addTenantDocumentApiV1TenantDocumentsPost(this.http, this.config.rootUrl, {
      body,
    }).pipe(map((res) => res.body));
  }

  replace(
    documentId: string,
    body: ReplaceComplianceDocumentRequest,
  ): Observable<ComplianceDocumentResponse> {
    return replaceComplianceDocumentApiV1ComplianceDocumentsDocumentIdPut(
      this.http,
      this.config.rootUrl,
      { document_id: documentId, body },
    ).pipe(map((res) => res.body));
  }

  verify(
    documentId: string,
    body: VerifyComplianceDocumentRequest,
  ): Observable<ComplianceDocumentResponse> {
    return verifyComplianceDocumentApiV1ComplianceDocumentsDocumentIdVerifyPost(
      this.http,
      this.config.rootUrl,
      { document_id: documentId, body },
    ).pipe(map((res) => res.body));
  }

  listComplianceDocuments(
    filter: ComplianceDocumentListFilter = {},
  ): Observable<ComplianceDocumentListResponse> {
    return listComplianceDocumentsApiV1ComplianceDocumentsGet(this.http, this.config.rootUrl, {
      owner_type: filter.owner_type,
      status: filter.status,
      expiry: filter.expiry,
      skip: filter.skip,
      limit: filter.limit,
    }).pipe(map((res) => res.body));
  }
}
