import 'decimal_json.dart';

/// Mirrors the backend's `OnlinePaymentResponse` (ADR-052) — one attempt to
/// pay for an order through a hosted Razorpay payment link.
class OnlinePaymentResponse {
  const OnlinePaymentResponse({
    required this.onlinePaymentId,
    required this.orderId,
    required this.amount,
    required this.currency,
    required this.status,
    required this.paymentUrl,
    required this.appliedToInvoice,
    required this.createdAt,
    this.invoiceId,
    this.expiresAt,
    this.paidAt,
    this.paymentMethod,
  });

  factory OnlinePaymentResponse.fromJson(Map<String, dynamic> json) =>
      OnlinePaymentResponse(
        onlinePaymentId: json['online_payment_id'] as String,
        orderId: json['order_id'] as String,
        invoiceId: json['invoice_id'] as String?,
        amount: asDouble(json['amount']),
        currency: json['currency'] as String,
        status: json['status'] as String,
        paymentUrl: json['payment_url'] as String,
        expiresAt: json['expires_at'] == null
            ? null
            : DateTime.parse(json['expires_at'] as String),
        paidAt: json['paid_at'] == null
            ? null
            : DateTime.parse(json['paid_at'] as String),
        paymentMethod: json['payment_method'] as String?,
        appliedToInvoice: json['applied_to_invoice'] as bool? ?? false,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  final String onlinePaymentId;
  final String orderId;
  final String? invoiceId;
  final double amount;
  final String currency;

  /// `created`, `paid`, `expired` or `cancelled`.
  final String status;

  /// Hosted checkout page to open in the browser.
  final String paymentUrl;
  final DateTime? expiresAt;
  final DateTime? paidAt;
  final String? paymentMethod;
  final bool appliedToInvoice;
  final DateTime createdAt;

  bool get isPaid => status == 'paid';
  bool get isOpen => status == 'created';
}
