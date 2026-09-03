/// One stop on a delivery route — mirrors the backend's `RouteStopResponse`.
class RouteStopSummary {
  const RouteStopSummary({
    required this.id,
    required this.orderId,
    required this.sequenceNumber,
    required this.status,
  });

  factory RouteStopSummary.fromJson(Map<String, dynamic> json) =>
      RouteStopSummary(
        id: json['id'] as String,
        orderId: json['order_id'] as String,
        sequenceNumber: json['sequence_number'] as int,
        status: json['status'] as String,
      );

  final String id;
  final String orderId;
  final int sequenceNumber;
  final String status;
}

/// One line of the van's load manifest — mirrors the backend's
/// `RouteLoadLineResponse`. Cylinder-type names are resolved client-side.
class RouteLoadLine {
  const RouteLoadLine({required this.cylinderTypeId, required this.quantity});

  factory RouteLoadLine.fromJson(Map<String, dynamic> json) => RouteLoadLine(
    cylinderTypeId: json['cylinder_type_id'] as String,
    quantity: (json['quantity'] as num).toInt(),
  );

  final String cylinderTypeId;
  final int quantity;
}

/// A delivery route — mirrors the backend's `RouteResponse`. Kept separate
/// from the dashboard's richer route model: the Driver App only needs the
/// status, the ordered stops and the van-load manifest.
class RouteSummary {
  const RouteSummary({
    required this.id,
    required this.status,
    required this.driverId,
    required this.vehicleId,
    required this.stops,
    this.date,
    this.loadedLines = const [],
    this.loadConfirmedAt,
  });

  factory RouteSummary.fromJson(Map<String, dynamic> json) => RouteSummary(
    id: json['id'] as String,
    status: json['status'] as String,
    driverId: json['driver_id'] as String,
    vehicleId: json['vehicle_id'] as String,
    date: json['date'] == null
        ? null
        : DateTime.tryParse(json['date'] as String),
    stops:
        (json['stops'] as List<dynamic>?)
            ?.map((e) => RouteStopSummary.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const [],
    loadedLines:
        (json['loaded_lines'] as List<dynamic>?)
            ?.map((e) => RouteLoadLine.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const [],
    loadConfirmedAt: json['load_confirmed_at'] == null
        ? null
        : DateTime.tryParse(json['load_confirmed_at'] as String),
  );

  final String id;
  final String status;
  final String driverId;
  final String vehicleId;
  final DateTime? date;
  final List<RouteStopSummary> stops;

  /// What the office loaded onto the van (empty until the route is loaded).
  final List<RouteLoadLine> loadedLines;

  /// When the driver confirmed the van matches [loadedLines], or `null`.
  final DateTime? loadConfirmedAt;

  /// `true` once the vehicle has departed — the only state in which the
  /// backend accepts location pings.
  bool get isInProgress => status == 'in_progress';

  /// `true` when the office has loaded the van but the driver hasn't yet
  /// confirmed it — drives the Today "check your van load" nudge.
  bool get isLoadPending => status == 'loaded' && loadConfirmedAt == null;
}

/// `POST /routes/{id}/location` body — one GPS reading from the Driver App.
class DriverLocationReport {
  const DriverLocationReport({
    required this.latitude,
    required this.longitude,
    this.heading,
    this.speedKph,
    this.accuracyM,
  });

  final double latitude;
  final double longitude;
  final double? heading;
  final double? speedKph;
  final double? accuracyM;

  Map<String, dynamic> toJson() => {
    'latitude': latitude,
    'longitude': longitude,
    if (heading != null) 'heading': heading,
    if (speedKph != null) 'speed_kph': speedKph,
    if (accuracyM != null) 'accuracy_m': accuracyM,
  };
}
