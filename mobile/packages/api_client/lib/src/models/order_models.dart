import 'customer_models.dart';
import 'decimal_json.dart';

class OrderLineResponse {
  const OrderLineResponse({
    required this.id,
    required this.cylinderTypeId,
    required this.quantityOrdered,
    required this.quantityDelivered,
    required this.quantityPending,
    required this.quantityCollectedEmpty,
    required this.isBackordered,
    this.unitPrice,
  });

  factory OrderLineResponse.fromJson(Map<String, dynamic> json) =>
      OrderLineResponse(
        id: json['id'] as String,
        cylinderTypeId: json['cylinder_type_id'] as String,
        quantityOrdered: json['quantity_ordered'] as int,
        quantityDelivered: json['quantity_delivered'] as int,
        quantityPending: json['quantity_pending'] as int,
        quantityCollectedEmpty: json['quantity_collected_empty'] as int,
        isBackordered: json['is_backordered'] as bool,
        unitPrice: asDoubleOrNull(json['unit_price']),
      );

  final String id;
  final String cylinderTypeId;
  final int quantityOrdered;
  final int quantityDelivered;
  final int quantityPending;
  final int quantityCollectedEmpty;
  final bool isBackordered;
  final double? unitPrice;
}

class OrderResponse {
  const OrderResponse({
    required this.id,
    this.orderNumber,
    required this.tenantId,
    required this.branchId,
    required this.customerId,
    required this.addressId,
    required this.deliveryAddress,
    required this.status,
    required this.bookingSource,
    this.paymentMethodPreference,
    required this.requestedDate,
    required this.metadata,
    this.routeStopId,
    this.totalAmount,
    required this.lines,
  });

  factory OrderResponse.fromJson(Map<String, dynamic> json) => OrderResponse(
    id: json['id'] as String,
    orderNumber: json['order_number'] as String?,
    tenantId: json['tenant_id'] as String,
    branchId: json['branch_id'] as String,
    customerId: json['customer_id'] as String,
    addressId: json['address_id'] as String,
    deliveryAddress: DeliveryAddressPayload.fromJson(
      json['delivery_address'] as Map<String, dynamic>,
    ),
    status: json['status'] as String,
    bookingSource: json['booking_source'] as String,
    paymentMethodPreference: json['payment_method_preference'] as String?,
    requestedDate: DateTime.parse(json['requested_date'] as String),
    metadata: json['metadata'] as Map<String, dynamic>,
    routeStopId: json['route_stop_id'] as String?,
    totalAmount: asDoubleOrNull(json['total_amount']),
    lines: (json['lines'] as List<dynamic>)
        .map((e) => OrderLineResponse.fromJson(e as Map<String, dynamic>))
        .toList(),
  );

  final String id;
  // Sequential, zero-padded (e.g. "ORD000044") — sorts correctly as a plain
  // string and, unlike `requestedDate` (an operational delivery-scheduling
  // field customers can set arbitrarily far in the future or leave in the
  // past), actually reflects when the order was *placed*. Nullable only
  // because the backend schema allows it; every order booked through this
  // app has one.
  final String? orderNumber;
  final String tenantId;
  final String branchId;
  final String customerId;
  final String addressId;
  final DeliveryAddressPayload deliveryAddress;
  final String status;
  final String bookingSource;
  final String? paymentMethodPreference;
  final DateTime requestedDate;
  final Map<String, dynamic> metadata;
  final String? routeStopId;
  final double? totalAmount;
  final List<OrderLineResponse> lines;
}

/// One driver GPS reading, from the order-tracking read model or a live
/// `driver.location` real-time message.
class DriverLocationSnapshot {
  const DriverLocationSnapshot({
    required this.latitude,
    required this.longitude,
    this.heading,
    this.speedKph,
    this.accuracyM,
    required this.recordedAt,
  });

  factory DriverLocationSnapshot.fromJson(Map<String, dynamic> json) =>
      DriverLocationSnapshot(
        latitude: (json['latitude'] as num).toDouble(),
        longitude: (json['longitude'] as num).toDouble(),
        heading: (json['heading'] as num?)?.toDouble(),
        speedKph: (json['speed_kph'] as num?)?.toDouble(),
        accuracyM: (json['accuracy_m'] as num?)?.toDouble(),
        recordedAt: DateTime.parse(json['recorded_at'] as String),
      );

  final double latitude;
  final double longitude;
  final double? heading;
  final double? speedKph;
  final double? accuracyM;
  final DateTime recordedAt;
}

/// The assigned driver + vehicle — mirrors the backend's `TrackingDriverInfo`.
class TrackingDriver {
  const TrackingDriver({
    required this.name,
    this.phoneNumber,
    this.vehicleNumber,
    this.vehicleModel,
  });

  factory TrackingDriver.fromJson(Map<String, dynamic> json) => TrackingDriver(
    name: json['name'] as String,
    phoneNumber: json['phone_number'] as String?,
    vehicleNumber: json['vehicle_number'] as String?,
    vehicleModel: json['vehicle_model'] as String?,
  );

  final String name;
  final String? phoneNumber;
  final String? vehicleNumber;
  final String? vehicleModel;
}

/// Mirrors the backend's `OrderTrackingResponse` — what the tracking map
/// needs beyond the order itself: the resolved route status, the driver's
/// last-known position (`driverLocation` is null until the driver starts
/// sharing), and the assigned driver + vehicle.
class OrderTrackingResponse {
  const OrderTrackingResponse({
    required this.orderId,
    required this.status,
    this.destinationLatitude,
    this.destinationLongitude,
    required this.destinationLabel,
    this.routeStatus,
    this.driverLocation,
    this.driver,
  });

  factory OrderTrackingResponse.fromJson(Map<String, dynamic> json) =>
      OrderTrackingResponse(
        orderId: json['order_id'] as String,
        status: json['status'] as String,
        destinationLatitude: (json['destination_latitude'] as num?)?.toDouble(),
        destinationLongitude: (json['destination_longitude'] as num?)
            ?.toDouble(),
        destinationLabel: json['destination_label'] as String,
        routeStatus: json['route_status'] as String?,
        driverLocation: json['driver_location'] == null
            ? null
            : DriverLocationSnapshot.fromJson(
                json['driver_location'] as Map<String, dynamic>,
              ),
        driver: json['driver'] == null
            ? null
            : TrackingDriver.fromJson(json['driver'] as Map<String, dynamic>),
      );

  final String orderId;
  final String status;
  final double? destinationLatitude;
  final double? destinationLongitude;
  final String destinationLabel;
  final String? routeStatus;
  final DriverLocationSnapshot? driverLocation;
  final TrackingDriver? driver;
}

/// One line of a `POST /orders/{id}/deliver` submission — mirrors the
/// backend's `DeliveredLineRequest`.
class DeliveredLineRequest {
  const DeliveredLineRequest({
    required this.cylinderTypeId,
    required this.quantityDelivered,
    this.quantityCollectedEmpty = 0,
  });

  final String cylinderTypeId;
  final int quantityDelivered;
  final int quantityCollectedEmpty;

  Map<String, dynamic> toJson() => {
    'cylinder_type_id': cylinderTypeId,
    'quantity_delivered': quantityDelivered,
    'quantity_collected_empty': quantityCollectedEmpty,
  };
}

/// Proof-of-delivery payload — mirrors the backend's
/// `ProofOfDeliverySubmission`. Every field is required.
class ProofOfDeliverySubmission {
  const ProofOfDeliverySubmission({
    required this.signatureBlobRef,
    required this.photoBlobRef,
    required this.gpsLat,
    required this.gpsLng,
    required this.paymentMethod,
    required this.amountCollected,
  });

  final String signatureBlobRef;
  final String photoBlobRef;
  final double gpsLat;
  final double gpsLng;
  final String paymentMethod;
  final double amountCollected;

  Map<String, dynamic> toJson() => {
    'signature_blob_ref': signatureBlobRef,
    'photo_blob_ref': photoBlobRef,
    'gps_lat': gpsLat,
    'gps_lng': gpsLng,
    'payment_method': paymentMethod,
    'amount_collected': amountCollected,
  };
}

/// `POST /orders/{id}/deliver` body — mirrors `DeliverOrderRequest`.
class DeliverOrderRequest {
  const DeliverOrderRequest({
    required this.lines,
    required this.otpCode,
    required this.proofOfDelivery,
  });

  final List<DeliveredLineRequest> lines;
  final String otpCode;
  final ProofOfDeliverySubmission proofOfDelivery;

  Map<String, dynamic> toJson() => {
    'lines': lines.map((l) => l.toJson()).toList(),
    'otp_code': otpCode,
    'proof_of_delivery': proofOfDelivery.toJson(),
  };
}

/// `POST /orders/{id}/pod-attachments` response.
class PodAttachmentResponse {
  const PodAttachmentResponse({required this.blobRef});

  factory PodAttachmentResponse.fromJson(Map<String, dynamic> json) =>
      PodAttachmentResponse(blobRef: json['blob_ref'] as String);

  final String blobRef;
}

/// `POST /orders/{id}/deliver` response — mirrors `DeliverOrderResponse`.
class DeliverOrderResponse {
  const DeliverOrderResponse({required this.order});

  factory DeliverOrderResponse.fromJson(Map<String, dynamic> json) =>
      DeliverOrderResponse(
        order: OrderResponse.fromJson(json['order'] as Map<String, dynamic>),
      );

  final OrderResponse order;
}

class OrderPageResponse {
  const OrderPageResponse({required this.items, required this.total});

  factory OrderPageResponse.fromJson(Map<String, dynamic> json) =>
      OrderPageResponse(
        items: (json['items'] as List<dynamic>)
            .map((e) => OrderResponse.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: json['total'] as int,
      );

  final List<OrderResponse> items;
  final int total;
}

/// One cylinder type + quantity line in a [CreateOrderRequest] — mirrors the
/// backend's `CreateOrderLineRequest`.
class CreateOrderLineRequest {
  const CreateOrderLineRequest({
    required this.cylinderTypeId,
    required this.quantity,
  });

  final String cylinderTypeId;
  final int quantity;

  Map<String, dynamic> toJson() => {
    'cylinder_type_id': cylinderTypeId,
    'quantity': quantity,
  };
}

/// `POST /orders` body — mirrors the backend's `CreateOrderRequest`. Every
/// field is required server-side (no partial/draft creation) — `branchId`
/// and `customerId` are typically pre-filled from the signed-in customer's
/// own profile rather than chosen in the UI.
class CreateOrderRequest {
  const CreateOrderRequest({
    required this.branchId,
    required this.customerId,
    required this.addressId,
    required this.deliveryAddress,
    required this.bookingSource,
    required this.requestedDate,
    required this.lines,
    this.paymentMethodPreference,
  });

  final String branchId;
  final String customerId;
  final String addressId;
  final DeliveryAddressPayload deliveryAddress;
  final String bookingSource;
  final DateTime requestedDate;
  final List<CreateOrderLineRequest> lines;
  final String? paymentMethodPreference;

  Map<String, dynamic> toJson() => {
    'branch_id': branchId,
    'customer_id': customerId,
    'address_id': addressId,
    'delivery_address': deliveryAddress.toJson(),
    'booking_source': bookingSource,
    'requested_date': requestedDate.toUtc().toIso8601String(),
    'lines': lines.map((line) => line.toJson()).toList(),
    if (paymentMethodPreference != null)
      'payment_method_preference': paymentMethodPreference,
  };
}

/// `POST /orders/{id}/cancel` body — mirrors the backend's
/// `CancelOrderRequest`.
class CancelOrderRequest {
  const CancelOrderRequest({required this.reason});

  final String reason;

  Map<String, dynamic> toJson() => {'reason': reason};
}

/// `POST /orders/{id}/cancel` response — mirrors the backend's
/// `CancelOrderResponse`. `pendingApproval` is true when the order had
/// already been dispatched: the order's own `status` is unchanged and a
/// Manager must approve the cancellation (D-19) — the UI should show
/// "Cancellation requested", not "Cancelled", in that case.
class CancelOrderResponse {
  const CancelOrderResponse({
    required this.order,
    required this.pendingApproval,
  });

  factory CancelOrderResponse.fromJson(Map<String, dynamic> json) =>
      CancelOrderResponse(
        order: OrderResponse.fromJson(json['order'] as Map<String, dynamic>),
        pendingApproval: json['pending_approval'] as bool,
      );

  final OrderResponse order;
  final bool pendingApproval;
}
