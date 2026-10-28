/// A scale in the registry — the fields the weighment form needs.
class ScaleSummary {
  const ScaleSummary({
    required this.id,
    required this.warehouseId,
    required this.assetTag,
    required this.isExpired,
  });

  factory ScaleSummary.fromJson(Map<String, dynamic> json) => ScaleSummary(
    id: json['id'] as String,
    warehouseId: json['warehouse_id'] as String,
    assetTag: json['asset_tag'] as String,
    isExpired: json['is_expired'] as bool? ?? false,
  );

  final String id;
  final String warehouseId;
  final String assetTag;

  /// The scale's calibration certificate has run out; the server refuses
  /// checks made on it.
  final bool isExpired;
}

/// One weighment check on file — mirrors `WeighmentRecordResponse`.
class WeighmentRecord {
  const WeighmentRecord({
    required this.cylinderTypeId,
    required this.context,
    required this.result,
    required this.cylindersChecked,
    required this.underweightCylinderCount,
  });

  factory WeighmentRecord.fromJson(Map<String, dynamic> json) =>
      WeighmentRecord(
        cylinderTypeId: json['cylinder_type_id'] as String,
        context: json['context'] as String,
        result: json['result'] as String,
        cylindersChecked: (json['cylinders_checked'] as num).toInt(),
        underweightCylinderCount: (json['underweight_cylinder_count'] as num)
            .toInt(),
      );

  final String cylinderTypeId;
  final String context;
  final String result;
  final int cylindersChecked;
  final int underweightCylinderCount;

  /// This check counts toward the load-out gate.
  bool get passesLoadOut =>
      context == 'load_out_full_check' && result == 'pass';
}
