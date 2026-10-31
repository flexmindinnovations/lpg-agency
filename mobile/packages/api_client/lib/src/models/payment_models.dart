import 'dart:convert';
import 'dart:typed_data';

import 'decimal_json.dart';

/// Mirrors the backend's `OnlinePaymentResponse` (ADR-053) — one attempt to
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
    this.provider = 'razorpay',
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
        provider: json['provider'] as String? ?? 'razorpay',
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

  /// `razorpay`, or `mock` for the keyless demo gateway.
  final String provider;

  bool get isPaid => status == 'paid';
  bool get isOpen => status == 'created';
}

/// The agency's bank and UPI details (`GET /payment-profile`, ADR-066).
class PaymentProfile {
  const PaymentProfile({
    this.accountHolder = '',
    this.bankName = '',
    this.accountNumber = '',
    this.ifsc = '',
    this.branch = '',
    this.upiId = '',
    this.upiPayeeName = '',
    this.invoiceFooterNote = '',
  });

  factory PaymentProfile.fromJson(Map<String, dynamic> json) => PaymentProfile(
    accountHolder: json['account_holder'] as String? ?? '',
    bankName: json['bank_name'] as String? ?? '',
    accountNumber: json['account_number'] as String? ?? '',
    ifsc: json['ifsc'] as String? ?? '',
    branch: json['branch'] as String? ?? '',
    upiId: json['upi_id'] as String? ?? '',
    upiPayeeName: json['upi_payee_name'] as String? ?? '',
    invoiceFooterNote: json['invoice_footer_note'] as String? ?? '',
  );

  final String accountHolder;
  final String bankName;
  final String accountNumber;
  final String ifsc;
  final String branch;
  final String upiId;
  final String upiPayeeName;
  final String invoiceFooterNote;

  bool get hasBankDetails => accountNumber.isNotEmpty && ifsc.isNotEmpty;
  bool get hasUpi => upiId.isNotEmpty;

  Map<String, dynamic> toJson() => {
    'account_holder': accountHolder,
    'bank_name': bankName,
    'account_number': accountNumber,
    'ifsc': ifsc,
    'branch': branch,
    'upi_id': upiId,
    'upi_payee_name': upiPayeeName,
    'invoice_footer_note': invoiceFooterNote,
  };
}

/// UPI pay link and QR for what is owed on an order or invoice
/// (`GET /payments/upi-qr`).
class UpiQr {
  const UpiQr({
    required this.upiUri,
    required this.upiId,
    required this.payeeName,
    required this.amount,
    required this.qrPngBase64,
  });

  factory UpiQr.fromJson(Map<String, dynamic> json) => UpiQr(
    upiUri: json['upi_uri'] as String,
    upiId: json['upi_id'] as String,
    payeeName: json['payee_name'] as String,
    amount: asDouble(json['amount']),
    qrPngBase64: json['qr_png_base64'] as String,
  );

  /// The `upi://pay` link — opens a UPI app when launched on a phone.
  final String upiUri;
  final String upiId;
  final String payeeName;
  final double amount;
  final String qrPngBase64;

  Uint8List get png => base64Decode(qrPngBase64);
}

/// One way of paying, as the agency offers it.
class PaymentMethodOption {
  const PaymentMethodOption({required this.code, required this.label});

  factory PaymentMethodOption.fromJson(Map<String, dynamic> json) =>
      PaymentMethodOption(
        code: json['code'] as String,
        label: json['label'] as String,
      );

  /// The backend's code (`cash`, `upi`, `online_gateway`, ...).
  final String code;
  final String label;
}

/// The ways of paying the agency offers (`GET /payments/methods`), worked out
/// by the server from its UPI ID, bank details and connected gateway.
class PaymentMethods {
  const PaymentMethods({
    required this.booking,
    required this.delivery,
    required this.office,
  });

  factory PaymentMethods.fromJson(Map<String, dynamic> json) {
    List<PaymentMethodOption> options(String key) => [
      for (final o in json[key] as List<dynamic>? ?? const [])
        PaymentMethodOption.fromJson(o as Map<String, dynamic>),
    ];
    return PaymentMethods(
      booking: options('booking'),
      delivery: options('delivery'),
      office: options('office'),
    );
  }

  /// Cash only, for when the agency's set-up could not be read: cash needs no
  /// provider, so it is always safe to offer.
  static const cashOnly = PaymentMethods(
    booking: [PaymentMethodOption(code: 'cash', label: 'Cash')],
    delivery: [PaymentMethodOption(code: 'cash', label: 'Cash')],
    office: [PaymentMethodOption(code: 'cash', label: 'Cash')],
  );

  /// What a customer may prefer when booking.
  final List<PaymentMethodOption> booking;

  /// What the driver may record at the door.
  final List<PaymentMethodOption> delivery;

  /// What the office may record against an invoice.
  final List<PaymentMethodOption> office;
}
