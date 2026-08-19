/// The `/auth/login`, `/auth/otp/verify`, `/auth/refresh` response shape —
/// mirrors the backend's `TokenResponse` schema
/// (`backend/src/lpg/api/v1/schemas/identity.py`).
class TokenPair {
  const TokenPair({required this.accessToken, this.refreshToken});

  factory TokenPair.fromJson(Map<String, dynamic> json) => TokenPair(
    accessToken: json['access_token'] as String,
    refreshToken: json['refresh_token'] as String?,
  );

  final String accessToken;

  /// Always present for mobile clients — the backend only omits it for the
  /// Dashboard's `HttpOnly` cookie flow (`TokenResponse`'s own docstring).
  final String? refreshToken;
}

/// `GET /auth/me` — mirrors the backend's `PrincipalResponse`.
class Principal {
  const Principal({
    required this.userId,
    required this.tenantId,
    required this.role,
    required this.permissions,
  });

  factory Principal.fromJson(Map<String, dynamic> json) => Principal(
    userId: json['user_id'] as String,
    tenantId: json['tenant_id'] as String?,
    role: json['role'] as String,
    permissions: (json['permissions'] as List<dynamic>).cast<String>().toSet(),
  );

  final String userId;
  final String? tenantId;
  final String role;
  final Set<String> permissions;
}

/// Mirrors the backend's `CustomerAddressResponse`.
class CustomerAddressResponse {
  const CustomerAddressResponse({
    required this.id,
    required this.line1,
    this.line2,
    this.landmark,
    this.area,
    this.city,
    this.district,
    this.state,
    this.pincode,
    required this.addressType,
    this.latitude,
    this.longitude,
    required this.isPrimary,
  });

  factory CustomerAddressResponse.fromJson(Map<String, dynamic> json) =>
      CustomerAddressResponse(
        id: json['id'] as String,
        line1: json['line_1'] as String,
        line2: json['line_2'] as String?,
        landmark: json['landmark'] as String?,
        area: json['area'] as String?,
        city: json['city'] as String?,
        district: json['district'] as String?,
        state: json['state'] as String?,
        pincode: json['pincode'] as String?,
        addressType: json['address_type'] as String,
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
        isPrimary: json['is_primary'] as bool,
      );

  final String id;
  final String line1;
  final String? line2;
  final String? landmark;
  final String? area;
  final String? city;
  final String? district;
  final String? state;
  final String? pincode;
  final String addressType;
  final double? latitude;
  final double? longitude;
  final bool isPrimary;
}

/// Mirrors the backend's `CustomerResponse`.
class CustomerResponse {
  const CustomerResponse({
    required this.id,
    required this.tenantId,
    required this.branchId,
    this.consumerNumber,
    required this.fullName,
    required this.phoneNumber,
    this.contactPerson,
    this.alternateMobile,
    this.email,
    this.dateOfBirth,
    required this.customerType,
    required this.kycStatus,
    required this.status,
    this.lpgSubsidyId,
    required this.addresses,
  });

  factory CustomerResponse.fromJson(Map<String, dynamic> json) =>
      CustomerResponse(
        id: json['id'] as String,
        tenantId: json['tenant_id'] as String,
        branchId: json['branch_id'] as String,
        consumerNumber: json['consumer_number'] as String?,
        fullName: json['full_name'] as String,
        phoneNumber: json['phone_number'] as String,
        contactPerson: json['contact_person'] as String?,
        alternateMobile: json['alternate_mobile'] as String?,
        email: json['email'] as String?,
        dateOfBirth: json['date_of_birth'] as String?,
        customerType: json['customer_type'] as String,
        kycStatus: json['kyc_status'] as String,
        status: json['status'] as String,
        lpgSubsidyId: json['lpg_subsidy_id'] as String?,
        addresses:
            (json['addresses'] as List<dynamic>?)
                ?.map(
                  (e) => CustomerAddressResponse.fromJson(
                    e as Map<String, dynamic>,
                  ),
                )
                .toList() ??
            const [],
      );

  final String id;
  final String tenantId;
  final String branchId;
  final String? consumerNumber;
  final String fullName;
  final String phoneNumber;
  final String? contactPerson;
  final String? alternateMobile;
  final String? email;
  final String? dateOfBirth;
  final String customerType;
  final String kycStatus;
  final String status;
  final String? lpgSubsidyId;
  final List<CustomerAddressResponse> addresses;
}

class DeliveryAddressPayload {
  const DeliveryAddressPayload({
    required this.addressLine,
    this.latitude,
    this.longitude,
  });

  factory DeliveryAddressPayload.fromJson(Map<String, dynamic> json) =>
      DeliveryAddressPayload(
        addressLine: json['address_line'] as String,
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
      );

  final String addressLine;
  final double? latitude;
  final double? longitude;
}

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
        unitPrice: (json['unit_price'] as num?)?.toDouble(),
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
    totalAmount: (json['total_amount'] as num?)?.toDouble(),
    lines: (json['lines'] as List<dynamic>)
        .map((e) => OrderLineResponse.fromJson(e as Map<String, dynamic>))
        .toList(),
  );

  final String id;
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

/// Request to update a customer profile.
class UpdateCustomerProfileRequest {
  const UpdateCustomerProfileRequest({
    required this.branchId,
    required this.fullName,
    required this.phoneNumber,
    this.contactPerson,
    this.alternateMobile,
    this.email,
    this.dateOfBirth,
    required this.customerType,
    required this.status,
    this.lpgSubsidyId,
  });

  final String branchId;
  final String fullName;
  final String phoneNumber;
  final String? contactPerson;
  final String? alternateMobile;
  final String? email;
  final String? dateOfBirth;
  final String customerType;
  final String status;
  final String? lpgSubsidyId;

  Map<String, dynamic> toJson() => {
    'branch_id': branchId,
    'full_name': fullName,
    'phone_number': phoneNumber,
    if (contactPerson != null) 'contact_person': contactPerson,
    if (alternateMobile != null) 'alternate_mobile': alternateMobile,
    if (email != null) 'email': email,
    if (dateOfBirth != null) 'date_of_birth': dateOfBirth,
    'customer_type': customerType,
    'status': status,
    if (lpgSubsidyId != null) 'lpg_subsidy_id': lpgSubsidyId,
  };
}

/// Request to add a customer address.
class AddCustomerAddressRequest {
  const AddCustomerAddressRequest({
    required this.line1,
    this.line2,
    this.landmark,
    this.area,
    this.city,
    this.district,
    this.state,
    this.pincode,
    this.addressType = 'delivery',
    this.latitude,
    this.longitude,
  });

  final String line1;
  final String? line2;
  final String? landmark;
  final String? area;
  final String? city;
  final String? district;
  final String? state;
  final String? pincode;
  final String addressType;
  final double? latitude;
  final double? longitude;

  Map<String, dynamic> toJson() => {
    'line_1': line1,
    if (line2 != null) 'line_2': line2,
    if (landmark != null) 'landmark': landmark,
    if (area != null) 'area': area,
    if (city != null) 'city': city,
    if (district != null) 'district': district,
    if (state != null) 'state': state,
    if (pincode != null) 'pincode': pincode,
    'address_type': addressType,
    if (latitude != null) 'latitude': latitude,
    if (longitude != null) 'longitude': longitude,
  };
}
