import 'decimal_json.dart';

/// One price on the list, mirroring `PriceListEntryResponse`. The list keeps
/// every price ever set, so a cylinder type, customer type and branch can
/// have several entries; the one in force is the latest whose
/// [effectiveFrom] has passed.
class PriceEntry {
  const PriceEntry({
    required this.id,
    required this.cylinderTypeId,
    required this.customerType,
    required this.price,
    required this.effectiveFrom,
    this.branchId,
  });

  factory PriceEntry.fromJson(Map<String, dynamic> json) => PriceEntry(
    id: json['id'] as String,
    cylinderTypeId: json['cylinder_type_id'] as String,
    customerType: json['customer_type'] as String,
    branchId: json['branch_id'] as String?,
    price: asDouble(json['price']),
    effectiveFrom: DateTime.parse(json['effective_from'] as String),
  );

  final String id;
  final String cylinderTypeId;

  /// `domestic`, `commercial`, `industrial` or `government`.
  final String customerType;

  /// `null` for the agency-wide default.
  final String? branchId;
  final double price;
  final DateTime effectiveFrom;
}

/// A rate change an oil company announced, waiting for the office to accept
/// or reject it, mirroring `PriceListProposalResponse`. Accepting makes it a
/// price from [effectiveFrom].
class PriceProposal {
  const PriceProposal({
    required this.id,
    required this.cylinderTypeId,
    required this.customerType,
    required this.proposedPrice,
    required this.effectiveFrom,
    required this.sourceUrl,
    this.branchId,
  });

  factory PriceProposal.fromJson(Map<String, dynamic> json) => PriceProposal(
    id: json['id'] as String,
    cylinderTypeId: json['cylinder_type_id'] as String,
    customerType: json['customer_type'] as String,
    branchId: json['branch_id'] as String?,
    proposedPrice: asDouble(json['proposed_price']),
    effectiveFrom: DateTime.parse(json['effective_from'] as String),
    sourceUrl: (json['source_url'] as String?) ?? '',
  );

  final String id;
  final String cylinderTypeId;
  final String customerType;
  final String? branchId;
  final double proposedPrice;
  final DateTime effectiveFrom;

  /// Where the number came from, so a reviewer can check it first.
  final String sourceUrl;
}
