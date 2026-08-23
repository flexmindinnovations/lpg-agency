import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { addAddressApiV1CustomersCustomerIdAddressesPost } from './generated/fn/customers/add-address-api-v-1-customers-customer-id-addresses-post';
import { getCustomerApiV1CustomersCustomerIdGet } from './generated/fn/customers/get-customer-api-v-1-customers-customer-id-get';
import { listCustomersApiV1CustomersGet } from './generated/fn/customers/list-customers-api-v-1-customers-get';
import { listKycDocumentsApiV1CustomersCustomerIdKycGet } from './generated/fn/customers/list-kyc-documents-api-v-1-customers-customer-id-kyc-get';
import { peekNextConsumerNumberApiV1CustomersNextConsumerNumberPost } from './generated/fn/customers/peek-next-consumer-number-api-v-1-customers-next-consumer-number-post';
import { registerCustomerApiV1CustomersPost } from './generated/fn/customers/register-customer-api-v-1-customers-post';
import { setPrimaryAddressApiV1CustomersCustomerIdAddressesAddressIdPrimaryPut } from './generated/fn/customers/set-primary-address-api-v-1-customers-customer-id-addresses-address-id-primary-put';
import { submitKycApiV1CustomersCustomerIdKycPost } from './generated/fn/customers/submit-kyc-api-v-1-customers-customer-id-kyc-post';
import { updateCustomerProfileApiV1CustomersCustomerIdPut } from './generated/fn/customers/update-customer-profile-api-v-1-customers-customer-id-put';
import { recognizeKycDocumentApiV1CustomersKycAttachmentsRecognizePost } from './generated/fn/customers/recognize-kyc-document-api-v-1-customers-kyc-attachments-recognize-post';
import { uploadKycAttachmentApiV1CustomersKycAttachmentsPost } from './generated/fn/customers/upload-kyc-attachment-api-v-1-customers-kyc-attachments-post';
import { verifyKycApiV1CustomersCustomerIdKycDocIdVerifyPost } from './generated/fn/customers/verify-kyc-api-v-1-customers-customer-id-kyc-doc-id-verify-post';
import { deleteOnboardingDraftApiV1CustomersOnboardingDraftsDraftIdDelete } from './generated/fn/customer-onboarding-drafts/delete-onboarding-draft-api-v-1-customers-onboarding-drafts-draft-id-delete';
import { getOnboardingDraftApiV1CustomersOnboardingDraftsDraftIdGet } from './generated/fn/customer-onboarding-drafts/get-onboarding-draft-api-v-1-customers-onboarding-drafts-draft-id-get';
import { listMyOnboardingDraftsApiV1CustomersOnboardingDraftsGet } from './generated/fn/customer-onboarding-drafts/list-my-onboarding-drafts-api-v-1-customers-onboarding-drafts-get';
import { saveOnboardingDraftApiV1CustomersOnboardingDraftsPost } from './generated/fn/customer-onboarding-drafts/save-onboarding-draft-api-v-1-customers-onboarding-drafts-post';
import type { AddCustomerAddressRequest } from './generated/models/add-customer-address-request';
import type { CustomerResponse } from './generated/models/customer-response';
import type { CustomerPageResponse } from './generated/models/customer-page-response';
import type { KycAttachmentResponse } from './generated/models/kyc-attachment-response';
import type { KycDocumentListResponse } from './generated/models/kyc-document-list-response';
import type { NextConsumerNumberResponse } from './generated/models/next-consumer-number-response';
import type { OnboardingDraftListResponse } from './generated/models/onboarding-draft-list-response';
import type { OnboardingDraftResponse } from './generated/models/onboarding-draft-response';
import type { RecognizeKycDocumentResponse } from './generated/models/recognize-kyc-document-response';
import type { RegisterCustomerRequest } from './generated/models/register-customer-request';
import type { SaveOnboardingDraftRequest } from './generated/models/save-onboarding-draft-request';
import type { UpdateCustomerProfileRequest } from './generated/models/update-customer-profile-request';

@Injectable({ providedIn: 'root' })
export class CustomerService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  peekNextConsumerNumber(): Observable<NextConsumerNumberResponse> {
    return peekNextConsumerNumberApiV1CustomersNextConsumerNumberPost(
      this.http,
      this.config.rootUrl,
    ).pipe(map((res) => res.body));
  }

  register(request: RegisterCustomerRequest): Observable<CustomerResponse> {
    return registerCustomerApiV1CustomersPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body));
  }

  list(skip = 0, limit = 100, search?: string): Observable<CustomerPageResponse> {
    return listCustomersApiV1CustomersGet(this.http, this.config.rootUrl, {
      skip,
      limit,
      search,
    }).pipe(map((res) => res.body));
  }

  get(customerId: string): Observable<CustomerResponse> {
    return getCustomerApiV1CustomersCustomerIdGet(this.http, this.config.rootUrl, {
      customer_id: customerId,
    }).pipe(map((res) => res.body));
  }

  update(customerId: string, request: UpdateCustomerProfileRequest): Observable<CustomerResponse> {
    return updateCustomerProfileApiV1CustomersCustomerIdPut(this.http, this.config.rootUrl, {
      customer_id: customerId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  addAddress(customerId: string, address: AddCustomerAddressRequest): Observable<string> {
    return addAddressApiV1CustomersCustomerIdAddressesPost(this.http, this.config.rootUrl, {
      customer_id: customerId,
      body: address,
    }).pipe(map((res) => res.body));
  }

  setPrimaryAddress(customerId: string, addressId: string): Observable<void> {
    return setPrimaryAddressApiV1CustomersCustomerIdAddressesAddressIdPrimaryPut(
      this.http,
      this.config.rootUrl,
      {
        customer_id: customerId,
        address_id: addressId,
      },
    ).pipe(map(() => undefined));
  }

  listKyc(customerId: string): Observable<KycDocumentListResponse> {
    return listKycDocumentsApiV1CustomersCustomerIdKycGet(this.http, this.config.rootUrl, {
      customer_id: customerId,
    }).pipe(map((res) => res.body));
  }

  submitKyc(
    customerId: string,
    docType: string,
    docReference: string,
    fileUrl?: string | null,
  ): Observable<string> {
    return submitKycApiV1CustomersCustomerIdKycPost(this.http, this.config.rootUrl, {
      customer_id: customerId,
      body: {
        doc_type: docType,
        document_number: docReference,
        file_url: fileUrl ?? undefined,
      },
    }).pipe(map((res) => res.body));
  }

  verifyKyc(customerId: string, docId: string, status: 'verified' | 'rejected'): Observable<void> {
    return verifyKycApiV1CustomersCustomerIdKycDocIdVerifyPost(this.http, this.config.rootUrl, {
      customer_id: customerId,
      doc_id: docId,
      body: { status },
    }).pipe(map(() => undefined));
  }

  uploadKycAttachment(file: File): Observable<KycAttachmentResponse> {
    return uploadKycAttachmentApiV1CustomersKycAttachmentsPost(this.http, this.config.rootUrl, {
      body: { file },
    }).pipe(map((res) => res.body));
  }

  recognizeKycDocument(blobRef: string): Observable<RecognizeKycDocumentResponse> {
    return recognizeKycDocumentApiV1CustomersKycAttachmentsRecognizePost(
      this.http,
      this.config.rootUrl,
      { body: { blob_ref: blobRef } },
    ).pipe(map((res) => res.body));
  }

  saveOnboardingDraft(request: SaveOnboardingDraftRequest): Observable<OnboardingDraftResponse> {
    return saveOnboardingDraftApiV1CustomersOnboardingDraftsPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body));
  }

  listMyOnboardingDrafts(): Observable<OnboardingDraftListResponse> {
    return listMyOnboardingDraftsApiV1CustomersOnboardingDraftsGet(
      this.http,
      this.config.rootUrl,
    ).pipe(map((res) => res.body));
  }

  getOnboardingDraft(draftId: string): Observable<OnboardingDraftResponse> {
    return getOnboardingDraftApiV1CustomersOnboardingDraftsDraftIdGet(
      this.http,
      this.config.rootUrl,
      { draft_id: draftId },
    ).pipe(map((res) => res.body));
  }

  deleteOnboardingDraft(draftId: string): Observable<void> {
    return deleteOnboardingDraftApiV1CustomersOnboardingDraftsDraftIdDelete(
      this.http,
      this.config.rootUrl,
      { draft_id: draftId },
    ).pipe(map(() => undefined));
  }
}
