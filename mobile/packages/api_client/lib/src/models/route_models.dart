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

/// A delivery route — mirrors the backend's `RouteResponse`. Kept separate
/// from the dashboard's richer route model: the Driver App only needs the
/// status and the ordered stops.
class RouteSummary {
  const RouteSummary({
    required this.id,
    required this.status,
    required this.driverId,
    required this.vehicleId,
    required this.stops,
    this.date,
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
  );

  final String id;
  final String status;
  final String driverId;
  final String vehicleId;
  final DateTime? date;
  final List<RouteStopSummary> stops;

  /// `true` once the vehicle has departed — the only state in which the
  /// backend accepts location pings.
  bool get isInProgress => status == 'in_progress';
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
