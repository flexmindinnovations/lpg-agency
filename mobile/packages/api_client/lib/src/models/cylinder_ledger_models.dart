class CylinderLedgerBalanceItem {
  const CylinderLedgerBalanceItem({
    required this.cylinderTypeId,
    required this.quantity,
  });

  factory CylinderLedgerBalanceItem.fromJson(Map<String, dynamic> json) =>
      CylinderLedgerBalanceItem(
        cylinderTypeId: json['cylinder_type_id'] as String,
        quantity: json['quantity'] as int,
      );

  final String cylinderTypeId;
  final int quantity;
}

class CylinderLedgerResponse {
  const CylinderLedgerResponse({
    required this.customerId,
    required this.balances,
  });

  factory CylinderLedgerResponse.fromJson(Map<String, dynamic> json) =>
      CylinderLedgerResponse(
        customerId: json['customer_id'] as String,
        balances: (json['balances'] as List<dynamic>)
            .map((e) => CylinderLedgerBalanceItem.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  final String customerId;
  final List<CylinderLedgerBalanceItem> balances;
}
