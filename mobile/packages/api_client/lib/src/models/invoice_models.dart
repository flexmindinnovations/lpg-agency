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
        unitPrice: (json['unit_price'] as num).toDouble(),
        subtotal: (json['subtotal'] as num).toDouble(),
        taxAmount: (json['tax_amount'] as num).toDouble(),
        totalAmount: (json['total_amount'] as num).toDouble(),
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
        amount: (json['amount'] as num).toDouble(),
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
        subtotal: (json['subtotal'] as num).toDouble(),
        taxAmount: (json['tax_amount'] as num).toDouble(),
        totalAmount: (json['total_amount'] as num).toDouble(),
        version: json['version'] as int,
        payments:
            (json['payments'] as List<dynamic>?)
                ?.map(
                  (e) => PaymentResponse.fromJson(e as Map<String, dynamic>),
                )
                .toList() ??
            const [],
        amountPaid: (json['amount_paid'] as num?)?.toDouble() ?? 0,
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
