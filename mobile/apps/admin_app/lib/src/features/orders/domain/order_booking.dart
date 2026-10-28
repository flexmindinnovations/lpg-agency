import 'package:api_client/api_client.dart';

/// How the booking reached the office, keyed by backend code (same choices
/// as the dashboard's New order form).
const bookingSources = {
  'staff': 'Staff',
  'phone': 'Phone',
  'walk_in': 'Walk-in',
  'whatsapp': 'WhatsApp',
};

/// One cylinder line on the New order form.
class BookingLine {
  const BookingLine({this.cylinderTypeId, this.quantity = 1});

  final String? cylinderTypeId;
  final int quantity;

  BookingLine copyWith({String? cylinderTypeId, int? quantity}) => BookingLine(
    cylinderTypeId: cylinderTypeId ?? this.cylinderTypeId,
    quantity: quantity ?? this.quantity,
  );
}

/// The first thing wrong with a booking, in the office's words, or `null`
/// when it can be sent. Mirrors what the server enforces: a customer, one of
/// their saved addresses, at least one line, each a different orderable
/// cylinder type with 1 or more cylinders and no more than the stock left.
String? bookingProblem({
  required CustomerResponse? customer,
  required String? addressId,
  required List<BookingLine> lines,
  required List<OrderableCylinderTypeResponse> orderable,
}) {
  if (customer == null) return 'Select a customer.';
  if (customer.addresses.isEmpty) {
    return 'This customer has no saved address. Add one before booking.';
  }
  if (addressId == null) return 'Select a delivery address.';
  if (lines.isEmpty) return 'Add a cylinder to the order.';
  final seen = <String>{};
  for (final line in lines) {
    final id = line.cylinderTypeId;
    if (id == null) return 'Select a cylinder type for every line.';
    if (!seen.add(id)) {
      return 'A cylinder type can only be on the order once. '
          'Raise its quantity instead.';
    }
    if (line.quantity < 1) return 'Quantity must be at least 1.';
    final match = orderable.where((o) => o.cylinderTypeId == id);
    if (match.isEmpty) {
      return 'That cylinder type can no longer be booked for this customer.';
    }
    final available = match.first.availableQuantity;
    if (line.quantity > available) {
      return 'Only $available ${match.first.name} '
          '${available == 1 ? 'is' : 'are'} in stock.';
    }
  }
  return null;
}

/// The address a booking starts with: the customer's primary, or their only
/// one (same as the dashboard).
CustomerAddressResponse? defaultAddress(CustomerResponse customer) {
  for (final a in customer.addresses) {
    if (a.isPrimary) return a;
  }
  return customer.addresses.length == 1 ? customer.addresses.first : null;
}

/// A readable one-line address.
String addressLabel(CustomerAddressResponse a) => [
  a.line1,
  a.line2,
  a.area,
  a.city,
].where((p) => p != null && p.trim().isNotEmpty).join(', ');

/// The delivery day as noon local time, so the date survives the trip to
/// UTC whichever way the office's offset falls (same as the dashboard).
DateTime deliveryDay(DateTime date) =>
    DateTime(date.year, date.month, date.day, 12);
