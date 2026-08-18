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
import { verifyKycApiV1CustomersCustomerIdKycDocIdVerifyPost } from './generated/fn/customers/verify-kyc-api-v-1-customers-customer-id-kyc-doc-id-verify-post';
import type { CustomerResponse } from './generated/models/customer-response';
import type { CustomerPageResponse } from './generated/models/customer-page-response';
import type { KycDocumentListResponse } from './generated/models/kyc-document-list-response';
import type { NextConsumerNumberResponse } from './generated/models/next-consumer-number-response';
import type { RegisterCustomerRequest } from './generated/models/register-customer-request';
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

  addAddress(
    customerId: string,
    addressLine: string,
    latitude?: number,
    longitude?: number,
  ): Observable<string> {
    return addAddressApiV1CustomersCustomerIdAddressesPost(this.http, this.config.rootUrl, {
      customer_id: customerId,
      body: {
        line_1: addressLine,
        latitude,
        longitude,
      },
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

  submitKyc(customerId: string, docType: string, docReference: string): Observable<string> {
    return submitKycApiV1CustomersCustomerIdKycPost(this.http, this.config.rootUrl, {
      customer_id: customerId,
      body: {
        doc_type: docType,
        document_number: docReference,
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
}
