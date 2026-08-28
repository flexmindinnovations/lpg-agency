import 'decimal_json.dart';

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
        latitude: asDoubleOrNull(json['latitude']),
        longitude: asDoubleOrNull(json['longitude']),
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

/// Mirrors the backend's `DeliveryAddressPayload` — the free-text address
/// snapshot stored on an order at booking time (distinct from
/// [CustomerAddressResponse], the customer's saved address book entry).
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

  Map<String, dynamic> toJson() => {
    'address_line': addressLine,
    if (latitude != null) 'latitude': latitude,
    if (longitude != null) 'longitude': longitude,
  };
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

/// Request to update an existing customer address (`PUT
/// /customers/{customer_id}/addresses/{address_id}`) — mirrors the backend's
/// `UpdateCustomerAddressRequest`. Same field set as [AddCustomerAddressRequest]
/// (a full replace, not a partial patch).
class UpdateCustomerAddressRequest {
  const UpdateCustomerAddressRequest({
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
