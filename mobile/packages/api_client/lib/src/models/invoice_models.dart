import 'decimal_json.dart';

/// Mirrors the backend's `InvoiceLineResponse`.
class InvoiceLineResponse {
  const InvoiceLineResponse({
    required this.lineId,
    required this.cylinderTypeId,
    required this.quantity,
    required this.unitPrice,
    required this.subtotal,
    required this.taxAmount,
    required this.totalAmount,
  });

  factory InvoiceLineResponse.fromJson(Map<String, dynamic> json) =>
      InvoiceLineResponse(
        lineId: json['line_id'] as String,
        cylinderTypeId: json['cylinder_type_id'] as String,
        quantity: json['quantity'] as int,
        unitPrice: asDouble(json['unit_price']),
        subtotal: asDouble(json['subtotal']),
        taxAmount: asDouble(json['tax_amount']),
        totalAmount: asDouble(json['total_amount']),
      );

  final String lineId;
  final String cylinderTypeId;
  final int quantity;
  final double unitPrice;
  final double subtotal;
  final double taxAmount;
  final double totalAmount;
}

/// Mirrors the backend's `PaymentResponse` — one recorded payment against an
/// invoice.
class PaymentResponse {
  const PaymentResponse({
    required this.paymentId,
    required this.method,
    required this.amount,
    required this.collectedBy,
    required this.collectedAt,
  });

  factory PaymentResponse.fromJson(Map<String, dynamic> json) =>
      PaymentResponse(
        paymentId: json['payment_id'] as String,
        method: json['method'] as String,
        amount: asDouble(json['amount']),
        collectedBy: json['collected_by'] as String,
        collectedAt: DateTime.parse(json['collected_at'] as String),
      );

  final String paymentId;
  final String method;
  final double amount;
  final String collectedBy;
  final DateTime collectedAt;
}

/// Mirrors the backend's `InvoiceResponse`. Field names on this response
/// (`invoiceId`, not `id`) are deliberately different from most other
/// response models — the router builds this field-by-field rather than via
/// `model_validate`, per `invoice.py`'s own `_invoice_to_response`.
class InvoiceResponse {
  const InvoiceResponse({
    required this.invoiceId,
    this.invoiceNumber,
    required this.tenantId,
    required this.customerId,
    this.customerConsumerNumber,
    required this.orderId,
    this.orderNumber,
    required this.status,
    required this.issuedAt,
    required this.lines,
    required this.subtotal,
    required this.taxAmount,
    required this.totalAmount,
    required this.version,
    this.payments = const [],
    this.amountPaid = 0,
    this.balanceDue = 0,
    this.customerName,
    this.customerGstin,
    this.isInterState = false,
    this.cgstAmount = 0,
    this.sgstAmount = 0,
    this.igstAmount = 0,
  });

  factory InvoiceResponse.fromJson(Map<String, dynamic> json) =>
      InvoiceResponse(
        invoiceId: json['invoice_id'] as String,
        invoiceNumber: json['invoice_number'] as String?,
        tenantId: json['tenant_id'] as String,
        customerId: json['customer_id'] as String,
        customerConsumerNumber: json['customer_consumer_number'] as String?,
        orderId: json['order_id'] as String,
        orderNumber: json['order_number'] as String?,
        status: json['status'] as String,
        issuedAt: DateTime.parse(json['issued_at'] as String),
        lines: (json['lines'] as List<dynamic>)
            .map((e) => InvoiceLineResponse.fromJson(e as Map<String, dynamic>))
            .toList(),
        subtotal: asDouble(json['subtotal']),
        taxAmount: asDouble(json['tax_amount']),
        totalAmount: asDouble(json['total_amount']),
        version: json['version'] as int,
        payments:
            (json['payments'] as List<dynamic>?)
                ?.map(
                  (e) => PaymentResponse.fromJson(e as Map<String, dynamic>),
                )
                .toList() ??
            const [],
        amountPaid: asDoubleOrNull(json['amount_paid']) ?? 0,
        balanceDue: asDoubleOrNull(json['balance_due']) ?? 0,
        customerName: json['customer_name'] as String?,
        customerGstin: json['customer_gstin'] as String?,
        isInterState: json['is_inter_state'] as bool? ?? false,
        cgstAmount: asDoubleOrNull(json['cgst_amount']) ?? 0,
        sgstAmount: asDoubleOrNull(json['sgst_amount']) ?? 0,
        igstAmount: asDoubleOrNull(json['igst_amount']) ?? 0,
      );

  final String invoiceId;
  final String? invoiceNumber;
  final String tenantId;
  final String customerId;
  final String? customerConsumerNumber;
  final String orderId;
  final String? orderNumber;
  final String status;
  final DateTime issuedAt;
  final List<InvoiceLineResponse> lines;
  final double subtotal;
  final double taxAmount;
  final double totalAmount;
  final int version;
  final List<PaymentResponse> payments;
  final double amountPaid;

  /// What is still owed (total less payments).
  final double balanceDue;
  final String? customerName;
  final String? customerGstin;

  /// CGST and SGST when the supplier and the place of supply are in one
  /// state, IGST when they differ.
  final bool isInterState;
  final double cgstAmount;
  final double sgstAmount;
  final double igstAmount;

  bool get isSettled => balanceDue <= 0 && status == 'paid';
}

/// `GET /invoices` pagination wrapper — mirrors the backend's
/// `InvoicePageResponse`. Note this is `{items, total, page, page_size}`
/// (1-indexed page), a different shape from [ComplaintListResponse]'s
/// `{items, total, skip, limit}`.
class InvoicePageResponse {
  const InvoicePageResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
  });

  factory InvoicePageResponse.fromJson(Map<String, dynamic> json) =>
      InvoicePageResponse(
        items: (json['items'] as List<dynamic>)
            .map((e) => InvoiceResponse.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: json['total'] as int,
        page: json['page'] as int,
        pageSize: json['page_size'] as int,
      );

  final List<InvoiceResponse> items;
  final int total;
  final int page;
  final int pageSize;
}
