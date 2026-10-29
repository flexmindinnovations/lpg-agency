import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

import { amendOrderApiV1OrdersOrderIdPatch } from './generated/fn/orders/amend-order-api-v-1-orders-order-id-patch';
import { getProofOfDeliveryApiV1OrdersOrderIdProofOfDeliveryGet } from './generated/fn/orders/get-proof-of-delivery-api-v-1-orders-order-id-proof-of-delivery-get';
import { rejectOrderCancellationApiV1OrdersOrderIdCancelRejectPost } from './generated/fn/orders/reject-order-cancellation-api-v-1-orders-order-id-cancel-reject-post';
import { approveOrderCancellationApiV1OrdersOrderIdCancelApprovePost } from './generated/fn/orders/approve-order-cancellation-api-v-1-orders-order-id-cancel-approve-post';
import { assignOrderApiV1OrdersOrderIdAssignPost } from './generated/fn/orders/assign-order-api-v-1-orders-order-id-assign-post';
import { bulkCancelOrdersApiV1OrdersBulkCancelPost } from './generated/fn/orders/bulk-cancel-orders-api-v-1-orders-bulk-cancel-post';
import { cancelOrderApiV1OrdersOrderIdCancelPost } from './generated/fn/orders/cancel-order-api-v-1-orders-order-id-cancel-post';
import { closeOrderApiV1OrdersOrderIdClosePost } from './generated/fn/orders/close-order-api-v-1-orders-order-id-close-post';
import { confirmOrderApiV1OrdersOrderIdConfirmPost } from './generated/fn/orders/confirm-order-api-v-1-orders-order-id-confirm-post';
import { createOrderApiV1OrdersPost } from './generated/fn/orders/create-order-api-v-1-orders-post';
import { departOrderApiV1OrdersOrderIdDepartPost } from './generated/fn/orders/depart-order-api-v-1-orders-order-id-depart-post';
import { deliverOrderApiV1OrdersOrderIdDeliverPost } from './generated/fn/orders/deliver-order-api-v-1-orders-order-id-deliver-post';
import { dispatchOrderApiV1OrdersOrderIdDispatchPost } from './generated/fn/orders/dispatch-order-api-v-1-orders-order-id-dispatch-post';
import { getOrderTrackingApiV1OrdersOrderIdTrackingGet } from './generated/fn/orders/get-order-tracking-api-v-1-orders-order-id-tracking-get';
import { listOrderRemindersApiV1OrdersOrderIdRemindersGet } from './generated/fn/orders/list-order-reminders-api-v-1-orders-order-id-reminders-get';
import { listReminderPresetsApiV1OrdersReminderPresetsGet } from './generated/fn/orders/list-reminder-presets-api-v-1-orders-reminder-presets-get';
import { sendOrderReminderApiV1OrdersOrderIdRemindersPost } from './generated/fn/orders/send-order-reminder-api-v-1-orders-order-id-reminders-post';
import { getOrderApiV1OrdersOrderIdGet } from './generated/fn/orders/get-order-api-v-1-orders-order-id-get';
import { getPendingCancellationApiV1OrdersOrderIdCancellationRequestGet } from './generated/fn/orders/get-pending-cancellation-api-v-1-orders-order-id-cancellation-request-get';
import { listOrderStatusHistoryApiV1OrdersOrderIdHistoryGet } from './generated/fn/orders/list-order-status-history-api-v-1-orders-order-id-history-get';
import { listOrderableCylinderTypesApiV1OrdersOrderableCylinderTypesGet } from './generated/fn/orders/list-orderable-cylinder-types-api-v-1-orders-orderable-cylinder-types-get';
import {
  listOrdersApiV1OrdersGet,
  type ListOrdersApiV1OrdersGet$Params,
} from './generated/fn/orders/list-orders-api-v-1-orders-get';
import { recordFailedDeliveryApiV1OrdersOrderIdFailedDeliveryPost } from './generated/fn/orders/record-failed-delivery-api-v-1-orders-order-id-failed-delivery-post';
import { rescheduleOrderApiV1OrdersOrderIdReschedulePost } from './generated/fn/orders/reschedule-order-api-v-1-orders-order-id-reschedule-post';
import { uploadPodAttachmentApiV1OrdersOrderIdPodAttachmentsPost } from './generated/fn/orders/upload-pod-attachment-api-v-1-orders-order-id-pod-attachments-post';

import type { LpgApiV1SchemasOrderAssignOrderRequest } from './generated/models/lpg-api-v-1-schemas-order-assign-order-request';
import type { AmendOrderRequest } from './generated/models/amend-order-request';
import type { OrderTrackingResponse } from './generated/models/order-tracking-response';
import type { ReminderPresetResponse } from './generated/models/reminder-preset-response';
import type { ReminderResponse } from './generated/models/reminder-response';
import type { SendReminderRequest } from './generated/models/send-reminder-request';
import type { ProofOfDeliveryResponse } from './generated/models/proof-of-delivery-response';
import type { BulkCancelOrdersRequest } from './generated/models/bulk-cancel-orders-request';
import type { BulkCancelOrdersResponse } from './generated/models/bulk-cancel-orders-response';
import type { CancelOrderRequest } from './generated/models/cancel-order-request';
import type { CancelOrderResponse } from './generated/models/cancel-order-response';
import type { CreateOrderRequest } from './generated/models/create-order-request';
import type { DeliverOrderRequest } from './generated/models/deliver-order-request';
import type { DeliverOrderResponse } from './generated/models/deliver-order-response';
import type { OrderPageResponse } from './generated/models/order-page-response';
import type { OrderableCylinderTypeResponse } from './generated/models/orderable-cylinder-type-response';
import type { OrderResponse } from './generated/models/order-response';
import type { OrderStatusHistoryEntryResponse } from './generated/models/order-status-history-entry-response';
import type { PendingCancellationResponse } from './generated/models/pending-cancellation-response';
import type { PodAttachmentResponse } from './generated/models/pod-attachment-response';
import type { RecordFailedDeliveryRequest } from './generated/models/record-failed-delivery-request';
import { randomUuid } from './random-uuid';

export type OrderStatusValue = NonNullable<ListOrdersApiV1OrdersGet$Params['status']>;

export interface ListOrdersParams {
  skip?: number;
  limit?: number;
  status?: OrderStatusValue;
  /** Order number, or the customer's name, phone or consumer number. */
  search?: string;
  /** ISO date-times bounding the delivery date (inclusive). */
  fromDate?: string;
  toDate?: string;
  customerId?: string;
}

/**
 * `createOrder`/`deliverOrder` bypass the generated functions for the
 * `Idempotency-Key` header — the backend reads it manually
 * (`request.headers.get(...)`), so it isn't part of the OpenAPI schema and
 * the generator never wires it into `RequestBuilder`. Everything else here
 * is the established thin-wrapper shape (see `inventory.service.ts`).
 */
@Injectable({ providedIn: 'root' })
export class OrderService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  // ---------------------------------------------------------------------------
  // Create / Read
  // ---------------------------------------------------------------------------

  createOrder(request: CreateOrderRequest): Observable<OrderResponse> {
    const headers = new HttpHeaders({ 'Idempotency-Key': randomUuid() });
    return this.http.post<OrderResponse>(
      `${this.config.rootUrl}${createOrderApiV1OrdersPost.PATH}`,
      request,
      { headers },
    );
  }

  /**
   * The cylinder types this customer can book right now at their branch:
   * active, priced for their customer type, and in stock. The server refuses
   * a booking for anything else, so the booking form offers only these.
   */
  listOrderableCylinderTypes(customerId: string): Observable<OrderableCylinderTypeResponse[]> {
    return listOrderableCylinderTypesApiV1OrdersOrderableCylinderTypesGet(
      this.http,
      this.config.rootUrl,
      { customer_id: customerId },
    ).pipe(map((res) => res.body));
  }

  listOrders(params: ListOrdersParams = {}): Observable<OrderPageResponse> {
    const search = params.search?.replace(/\s+/g, ' ').trim();
    return listOrdersApiV1OrdersGet(this.http, this.config.rootUrl, {
      skip: params.skip,
      limit: params.limit,
      status: params.status,
      search: search || undefined,
      from_date: params.fromDate,
      to_date: params.toDate,
      customer_id: params.customerId,
    }).pipe(map((res) => res.body));
  }

  /** Edit a booked or confirmed order before it is put on a trip. */
  amendOrder(orderId: string, request: AmendOrderRequest): Observable<OrderResponse> {
    return amendOrderApiV1OrdersOrderIdPatch(this.http, this.config.rootUrl, {
      order_id: orderId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  /** The delivery record of a delivered order, or `null` before delivery. */
  getProofOfDelivery(orderId: string): Observable<ProofOfDeliveryResponse | null> {
    return getProofOfDeliveryApiV1OrdersOrderIdProofOfDeliveryGet(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body ?? null));
  }

  getOrder(orderId: string): Observable<OrderResponse> {
    return getOrderApiV1OrdersOrderIdGet(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }

  /** Driver, van and the driver's last-known position for an order on a trip. */
  getOrderTracking(orderId: string): Observable<OrderTrackingResponse> {
    return getOrderTrackingApiV1OrdersOrderIdTrackingGet(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }

  listReminderPresets(): Observable<ReminderPresetResponse[]> {
    return listReminderPresetsApiV1OrdersReminderPresetsGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  listOrderReminders(orderId: string): Observable<ReminderResponse[]> {
    return listOrderRemindersApiV1OrdersOrderIdRemindersGet(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }

  /** Push a reminder to the customer's app; recorded on the order's timeline. */
  sendOrderReminder(orderId: string, request: SendReminderRequest): Observable<ReminderResponse> {
    return sendOrderReminderApiV1OrdersOrderIdRemindersPost(this.http, this.config.rootUrl, {
      order_id: orderId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  listOrderStatusHistory(orderId: string): Observable<OrderStatusHistoryEntryResponse[]> {
    return listOrderStatusHistoryApiV1OrdersOrderIdHistoryGet(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Confirm / Assign / Dispatch / Depart / Reschedule
  // ---------------------------------------------------------------------------

  confirmOrder(orderId: string): Observable<OrderResponse> {
    return confirmOrderApiV1OrdersOrderIdConfirmPost(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }

  assignOrder(
    orderId: string,
    request: LpgApiV1SchemasOrderAssignOrderRequest,
  ): Observable<OrderResponse> {
    return assignOrderApiV1OrdersOrderIdAssignPost(this.http, this.config.rootUrl, {
      order_id: orderId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  dispatchOrder(orderId: string): Observable<OrderResponse> {
    return dispatchOrderApiV1OrdersOrderIdDispatchPost(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }

  departOrder(orderId: string): Observable<OrderResponse> {
    return departOrderApiV1OrdersOrderIdDepartPost(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }

  /**
   * Without a date: retry on the same trip. With `requestedDate` (ISO): the
   * order leaves its trip and waits to be planned for that day.
   */
  rescheduleOrder(orderId: string, requestedDate?: string): Observable<OrderResponse> {
    return rescheduleOrderApiV1OrdersOrderIdReschedulePost(this.http, this.config.rootUrl, {
      order_id: orderId,
      body: requestedDate ? { requested_date: requestedDate } : null,
    }).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Proof of delivery / Deliver / Failed delivery
  // ---------------------------------------------------------------------------

  uploadPodAttachment(orderId: string, file: File): Observable<PodAttachmentResponse> {
    return uploadPodAttachmentApiV1OrdersOrderIdPodAttachmentsPost(this.http, this.config.rootUrl, {
      order_id: orderId,
      body: { file },
    }).pipe(map((res) => res.body));
  }

  deliverOrder(orderId: string, request: DeliverOrderRequest): Observable<DeliverOrderResponse> {
    const headers = new HttpHeaders({ 'Idempotency-Key': randomUuid() });
    return this.http.post<DeliverOrderResponse>(
      `${this.config.rootUrl}${deliverOrderApiV1OrdersOrderIdDeliverPost.PATH.replace('{order_id}', orderId)}`,
      request,
      { headers },
    );
  }

  recordFailedDelivery(
    orderId: string,
    request: RecordFailedDeliveryRequest,
  ): Observable<OrderResponse> {
    return recordFailedDeliveryApiV1OrdersOrderIdFailedDeliveryPost(
      this.http,
      this.config.rootUrl,
      {
        order_id: orderId,
        body: request,
      },
    ).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Cancellation
  // ---------------------------------------------------------------------------

  cancelOrder(orderId: string, request: CancelOrderRequest): Observable<CancelOrderResponse> {
    return cancelOrderApiV1OrdersOrderIdCancelPost(this.http, this.config.rootUrl, {
      order_id: orderId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  /** The cancellation request waiting for Manager approval, or `null`. */
  getPendingCancellation(orderId: string): Observable<PendingCancellationResponse | null> {
    return getPendingCancellationApiV1OrdersOrderIdCancellationRequestGet(
      this.http,
      this.config.rootUrl,
      { order_id: orderId },
    ).pipe(map((res) => res.body ?? null));
  }

  /** Decline a waiting post-dispatch cancellation request, with a reason. */
  rejectOrderCancellation(
    orderId: string,
    reason: string,
  ): Observable<PendingCancellationResponse> {
    return rejectOrderCancellationApiV1OrdersOrderIdCancelRejectPost(
      this.http,
      this.config.rootUrl,
      { order_id: orderId, body: { reason } },
    ).pipe(map((res) => res.body));
  }

  approveOrderCancellation(orderId: string): Observable<OrderResponse> {
    return approveOrderCancellationApiV1OrdersOrderIdCancelApprovePost(
      this.http,
      this.config.rootUrl,
      {
        order_id: orderId,
      },
    ).pipe(map((res) => res.body));
  }

  bulkCancelOrders(request: BulkCancelOrdersRequest): Observable<BulkCancelOrdersResponse> {
    return bulkCancelOrdersApiV1OrdersBulkCancelPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Close
  // ---------------------------------------------------------------------------

  closeOrder(orderId: string): Observable<OrderResponse> {
    return closeOrderApiV1OrdersOrderIdClosePost(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }
}
