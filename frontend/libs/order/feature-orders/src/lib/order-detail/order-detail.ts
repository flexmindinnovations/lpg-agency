import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, ElementRef, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { InputGroup } from 'primeng/inputgroup';
import { InputGroupAddon } from 'primeng/inputgroupaddon';
import { InputNumber } from 'primeng/inputnumber';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Textarea } from 'primeng/textarea';
import { Tooltip } from 'primeng/tooltip';
import {
  AdminCylinderTypeService,
  DeliveryService,
  OrderService,
  type CylinderTypeResponse,
  type DriverResponse,
  type RecordFailedDeliveryRequest,
  type OrderResponse,
  type OrderStatusHistoryEntryResponse,
  type ProofOfDeliverySubmission,
  type VehicleResponse,
} from '@lpg/shared/data-access';
import { errorMessageFor, statusLabel, statusSeverity } from '../order-status.util';

const FREE_CANCEL_STATUSES = new Set(['booked', 'confirmed', 'assigned', 'ready_for_dispatch']);
const APPROVAL_CANCEL_STATUSES = new Set(['out_for_delivery', 'failed_delivery']);

const FAILED_DELIVERY_REASONS = [
  { label: 'Customer unavailable', value: 'customer_unavailable' },
  { label: 'Wrong address', value: 'wrong_address' },
  { label: 'Payment refused', value: 'payment_refused' },
  { label: 'Vehicle issue', value: 'vehicle_issue' },
  { label: 'Safety issue', value: 'safety_issue' },
] as const;

const RESOLUTION_ACTIONS = [
  { label: 'Reschedule', value: 'reschedule' },
  { label: 'Cancel', value: 'cancel' },
  { label: 'Return stock', value: 'return_stock' },
] as const;

const PAYMENT_METHODS = [
  { label: 'Cash', value: 'cash' },
  { label: 'UPI', value: 'upi' },
  { label: 'Card', value: 'card' },
  { label: 'Online Gateway', value: 'online_gateway' },
  { label: 'Credit', value: 'credit' },
] as const;

@Component({
  selector: 'lpg-order-detail',
  standalone: true,
  imports: [HeaderTitlePortalDirective, 
    DatePipe,
    DecimalPipe,
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    Drawer,
    InputGroup,
    InputGroupAddon,
    InputNumber,
    InputText,
    Message,
    Select,
    Tag,
    Textarea,
    Tooltip,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './order-detail.html',
  styleUrl: './order-detail.css',
})
export class OrderDetail implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly orderService = inject(OrderService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly deliveryService = inject(DeliveryService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly order = signal<OrderResponse | null>(null);
  protected readonly history = signal<OrderStatusHistoryEntryResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly drivers = signal<DriverResponse[]>([]);
  protected readonly vehicles = signal<VehicleResponse[]>([]);

  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly infoMessage = signal<string | null>(null);

  protected readonly showCancelDialog = signal(false);
  protected readonly showAssignDrawer = signal(false);
  protected readonly showFailedDeliveryDrawer = signal(false);
  protected readonly showDeliverDrawer = signal(false);

  protected readonly assignTrigger = viewChild<ElementRef<HTMLButtonElement>>('assignTriggerEl');
  protected readonly failedDeliveryTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('failedDeliveryTriggerEl');
  protected readonly deliverTrigger = viewChild<ElementRef<HTMLButtonElement>>('deliverTriggerEl');

  protected readonly cylinderTypeNameById = computed(() => {
    const map = new Map<string, string>();
    for (const ct of this.cylinderTypes()) map.set(ct.id, ct.name);
    return map;
  });

  protected readonly canCancelFree = computed(() => {
    const status = this.order()?.status;
    return !!status && FREE_CANCEL_STATUSES.has(status);
  });

  protected readonly requiresCancelApproval = computed(() => {
    const status = this.order()?.status;
    return !!status && APPROVAL_CANCEL_STATUSES.has(status);
  });

  protected readonly canConfirm = computed(() => this.order()?.status === 'booked');
  protected readonly canAssign = computed(() => this.order()?.status === 'confirmed');
  protected readonly canDispatch = computed(() => this.order()?.status === 'assigned');
  protected readonly canDepart = computed(() => this.order()?.status === 'ready_for_dispatch');
  protected readonly canDeliverOrFail = computed(() => this.order()?.status === 'out_for_delivery');
  protected readonly canReschedule = computed(() => this.order()?.status === 'failed_delivery');
  protected readonly canClose = computed(() => this.order()?.status === 'delivered');

  protected readonly cancelForm = this.fb.group({
    reason: ['', [Validators.required, Validators.minLength(3)]],
  });

  protected readonly assignForm = this.fb.group({
    driver_id: ['', [Validators.required]],
    vehicle_id: ['', [Validators.required]],
  });

  protected readonly failedDeliveryForm = this.fb.group({
    reason_code: ['customer_unavailable', [Validators.required]],
    resolution_action: ['reschedule', [Validators.required]],
  });

  protected readonly deliverForm = this.fb.group({
    otp_code: ['', [Validators.required]],
    payment_method: ['cash', [Validators.required]],
    amount_collected: [0, [Validators.required, Validators.min(0)]],
    gps_lat: [0, [Validators.required]],
    gps_lng: [0, [Validators.required]],
    lines: this.fb.array<ReturnType<typeof this.buildDeliverLineGroup>>([]),
  });

  protected readonly signatureBlobRef = signal<string | null>(null);
  protected readonly photoBlobRef = signal<string | null>(null);
  protected readonly uploadingSignature = signal(false);
  protected readonly uploadingPhoto = signal(false);
  protected readonly gpsCaptured = signal(false);

  protected readonly signatureCanvas =
    viewChild<ElementRef<HTMLCanvasElement>>('signatureCanvas');
  private drawing = false;
  private hasSignatureStrokes = false;

  protected readonly deliverReady = computed(
    () => !!this.signatureBlobRef() && !!this.photoBlobRef() && this.gpsCaptured(),
  );

  protected readonly statusLabel = statusLabel;
  protected readonly statusSeverity = statusSeverity;
  protected readonly failedDeliveryReasons = [...FAILED_DELIVERY_REASONS];
  protected readonly resolutionActions = [...RESOLUTION_ACTIONS];
  protected readonly paymentMethods = [...PAYMENT_METHODS];

  ngOnInit(): void {
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (ct) => this.cylinderTypes.set(ct),
    });
    this.route.paramMap.subscribe((params) => {
      const orderId = params.get('id');
      if (orderId) this.load(orderId);
    });
  }

  private load(orderId: string): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.orderService.getOrder(orderId).subscribe({
      next: (order) => {
        this.order.set(order);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
    this.orderService.listOrderStatusHistory(orderId).subscribe({
      next: (entries) => this.history.set(entries),
      error: () => this.history.set([]),
    });
  }

  protected refresh(): void {
    const orderId = this.order()?.id;
    if (orderId) this.load(orderId);
  }

  private applyUpdate(order: OrderResponse, message: string): void {
    this.order.set(order);
    this.infoMessage.set(message);
    this.errorMessage.set(null);
    this.loading.set(false);
    this.refresh();
  }

  private applyError(err: unknown): void {
    this.errorMessage.set(errorMessageFor(err));
    this.loading.set(false);
  }

  // ---------------------------------------------------------------------------
  // Confirm / Dispatch / Depart / Reschedule / Close — direct status advances
  // ---------------------------------------------------------------------------

  protected onConfirm(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.confirmOrder(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Order confirmed.'),
      error: (err) => this.applyError(err),
    });
  }

  protected onDispatch(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.dispatchOrder(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Order marked ready for dispatch.'),
      error: (err) => this.applyError(err),
    });
  }

  protected onDepart(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.departOrder(order.id).subscribe({
      next: (updated) =>
        this.applyUpdate(updated, 'Driver departed — delivery OTP sent to the customer.'),
      error: (err) => this.applyError(err),
    });
  }

  protected onReschedule(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.rescheduleOrder(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Delivery rescheduled.'),
      error: (err) => this.applyError(err),
    });
  }

  protected onClose(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.closeOrder(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Order closed.'),
      error: (err) => this.applyError(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Assign
  // ---------------------------------------------------------------------------

  protected openAssignDrawer(): void {
    const order = this.order();
    this.assignForm.reset({ driver_id: '', vehicle_id: '' });
    this.deliveryService.listDrivers(0, 200, undefined, 'active', order?.branch_id).subscribe({
      next: (page) => this.drivers.set(page.items),
    });
    this.deliveryService.listVehicles(0, 200, undefined, 'active', order?.branch_id).subscribe({
      next: (page) => this.vehicles.set(page.items),
    });
    this.showAssignDrawer.set(true);
  }

  protected onSubmitAssign(): void {
    const order = this.order();
    if (!order || this.assignForm.invalid) return;
    const { driver_id, vehicle_id } = this.assignForm.getRawValue();
    this.loading.set(true);
    this.orderService.assignOrder(order.id, { driver_id, vehicle_id }).subscribe({
      next: (updated) => {
        this.showAssignDrawer.set(false);
        this.applyUpdate(updated, 'Order assigned to driver and vehicle.');
      },
      error: (err) => this.applyError(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Failed delivery
  // ---------------------------------------------------------------------------

  protected openFailedDeliveryDrawer(): void {
    this.failedDeliveryForm.reset({
      reason_code: 'customer_unavailable',
      resolution_action: 'reschedule',
    });
    this.showFailedDeliveryDrawer.set(true);
  }

  protected onSubmitFailedDelivery(): void {
    const order = this.order();
    if (!order || this.failedDeliveryForm.invalid) return;
    const { reason_code, resolution_action } = this.failedDeliveryForm.getRawValue();
    this.loading.set(true);
    const request: RecordFailedDeliveryRequest = {
      reason_code: reason_code as RecordFailedDeliveryRequest['reason_code'],
      resolution_action:
        resolution_action as RecordFailedDeliveryRequest['resolution_action'],
    };
    this.orderService.recordFailedDelivery(order.id, request).subscribe({
      next: (updated) => {
        this.showFailedDeliveryDrawer.set(false);
        this.applyUpdate(updated, 'Failed delivery recorded.');
      },
      error: (err) => this.applyError(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Deliver (OTP + Proof of Delivery: signature pad, photo, GPS)
  // ---------------------------------------------------------------------------

  private buildDeliverLineGroup(cylinderTypeId: string, maxQuantity: number) {
    return this.fb.group({
      cylinder_type_id: [cylinderTypeId],
      quantity_delivered: [maxQuantity, [Validators.required, Validators.min(0)]],
      quantity_collected_empty: [0, [Validators.required, Validators.min(0)]],
    });
  }

  protected get deliverLines() {
    return this.deliverForm.controls.lines;
  }

  protected openDeliverDrawer(): void {
    const order = this.order();
    if (!order) return;
    this.deliverForm.reset({
      otp_code: '',
      payment_method: 'cash',
      amount_collected: 0,
      gps_lat: 0,
      gps_lng: 0,
    });
    this.deliverForm.controls.lines.clear();
    for (const line of order.lines) {
      this.deliverForm.controls.lines.push(
        this.buildDeliverLineGroup(line.cylinder_type_id, line.quantity_ordered - line.quantity_pending),
      );
    }
    this.signatureBlobRef.set(null);
    this.photoBlobRef.set(null);
    this.gpsCaptured.set(false);
    this.hasSignatureStrokes = false;
    this.showDeliverDrawer.set(true);
    // The canvas isn't in the DOM until the drawer's content projects it.
    queueMicrotask(() => this.clearSignature());
  }

  protected captureLocation(): void {
    if (!navigator.geolocation) {
      this.errorMessage.set('Geolocation is not available on this device.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.deliverForm.patchValue({
          gps_lat: position.coords.latitude,
          gps_lng: position.coords.longitude,
        });
        this.gpsCaptured.set(true);
      },
      () => this.errorMessage.set('Could not read the device location.'),
    );
  }

  // --- Signature pad -------------------------------------------------------

  protected onSignatureDown(event: PointerEvent): void {
    const canvas = this.signatureCanvas()?.nativeElement;
    if (!canvas) return;
    this.drawing = true;
    const rect = canvas.getBoundingClientRect();
    const ctx = canvas.getContext('2d');
    ctx?.beginPath();
    ctx?.moveTo(event.clientX - rect.left, event.clientY - rect.top);
  }

  protected onSignatureMove(event: PointerEvent): void {
    if (!this.drawing) return;
    const canvas = this.signatureCanvas()?.nativeElement;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#000';
    ctx.lineTo(event.clientX - rect.left, event.clientY - rect.top);
    ctx.stroke();
    this.hasSignatureStrokes = true;
  }

  protected onSignatureUp(): void {
    this.drawing = false;
  }

  protected clearSignature(): void {
    const canvas = this.signatureCanvas()?.nativeElement;
    if (!canvas) return;
    canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
    this.hasSignatureStrokes = false;
    this.signatureBlobRef.set(null);
  }

  protected uploadSignature(): void {
    const order = this.order();
    const canvas = this.signatureCanvas()?.nativeElement;
    if (!order || !canvas || !this.hasSignatureStrokes) return;
    this.uploadingSignature.set(true);
    canvas.toBlob((blob) => {
      if (!blob) {
        this.uploadingSignature.set(false);
        return;
      }
      const file = new File([blob], 'signature.png', { type: 'image/png' });
      this.orderService.uploadPodAttachment(order.id, file).subscribe({
        next: (res) => {
          this.signatureBlobRef.set(res.blob_ref);
          this.uploadingSignature.set(false);
        },
        error: (err) => {
          this.applyError(err);
          this.uploadingSignature.set(false);
        },
      });
    }, 'image/png');
  }

  // --- Photo -----------------------------------------------------------------

  protected onPhotoSelected(event: Event): void {
    const order = this.order();
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!order || !file) return;
    this.uploadingPhoto.set(true);
    this.orderService.uploadPodAttachment(order.id, file).subscribe({
      next: (res) => {
        this.photoBlobRef.set(res.blob_ref);
        this.uploadingPhoto.set(false);
      },
      error: (err) => {
        this.applyError(err);
        this.uploadingPhoto.set(false);
      },
    });
  }

  protected onSubmitDeliver(): void {
    const order = this.order();
    const signatureBlobRef = this.signatureBlobRef();
    const photoBlobRef = this.photoBlobRef();
    if (!order || !signatureBlobRef || !photoBlobRef || this.deliverForm.invalid) return;
    const val = this.deliverForm.getRawValue();
    this.loading.set(true);
    const proofOfDelivery: ProofOfDeliverySubmission = {
      signature_blob_ref: signatureBlobRef,
      photo_blob_ref: photoBlobRef,
      gps_lat: val.gps_lat,
      gps_lng: val.gps_lng,
      payment_method: val.payment_method as ProofOfDeliverySubmission['payment_method'],
      amount_collected: val.amount_collected,
    };
    this.orderService
      .deliverOrder(order.id, {
        otp_code: val.otp_code,
        lines: val.lines.map((line) => ({
          cylinder_type_id: line.cylinder_type_id,
          quantity_delivered: line.quantity_delivered,
          quantity_collected_empty: line.quantity_collected_empty,
        })),
        proof_of_delivery: proofOfDelivery,
      })
      .subscribe({
        next: (result) => {
          this.showDeliverDrawer.set(false);
          this.applyUpdate(result.order, 'Delivery recorded.');
        },
        error: (err) => this.applyError(err),
      });
  }

  // ---------------------------------------------------------------------------
  // Cancel / Approve
  // ---------------------------------------------------------------------------

  protected openCancelDialog(): void {
    this.cancelForm.reset({ reason: '' });
    this.showCancelDialog.set(true);
  }

  protected onSubmitCancel(): void {
    const order = this.order();
    if (!order || this.cancelForm.invalid) return;
    const { reason } = this.cancelForm.getRawValue();
    this.loading.set(true);
    this.orderService.cancelOrder(order.id, { reason }).subscribe({
      next: (result) => {
        this.showCancelDialog.set(false);
        this.infoMessage.set(
          result.pending_approval
            ? 'Cancellation requested — awaiting Manager approval.'
            : 'Order cancelled.',
        );
        this.order.set(result.order);
        this.loading.set(false);
        this.refresh();
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected onApproveCancellation(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.approveOrderCancellation(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Cancellation approved.'),
      error: (err) => this.applyError(err),
    });
  }

  protected backToQueue(): void {
    void this.router.navigate(['/orders']);
  }
}
