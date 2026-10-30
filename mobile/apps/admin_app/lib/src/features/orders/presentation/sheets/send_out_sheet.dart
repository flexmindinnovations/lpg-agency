import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../api_result.dart';
import '../../../../providers.dart';
import '../../../dispatch/data/dispatch_provider.dart';
import '../../../dispatch/domain/trip_status.dart';
import '../../data/orders_provider.dart';
import '../../domain/order_flow.dart';
import 'weighment_section.dart';

const _newTrip = 'new';

/// The trip sheet for one order: pick a driver and van (or an open trip) and
/// the godown, check the cylinders against stock, then load and hand the van
/// to the driver in one step (`POST /routes/{id}/load-and-dispatch`, ADR-056).
/// Pops `true` when the order went out.
class SendOutSheet extends ConsumerStatefulWidget {
  const SendOutSheet({super.key, required this.order, this.currentTrip});

  final OrderResponse order;

  /// The open trip the order is already on (status "assigned"), if known.
  final RouteSummary? currentTrip;

  @override
  ConsumerState<SendOutSheet> createState() => _SendOutSheetState();
}

class _SendOutSheetState extends ConsumerState<SendOutSheet> {
  String _tripId = _newTrip;
  String? _driverId;
  String? _vehicleId;
  String? _warehouseId;
  String? _error;
  bool _busy = false;

  /// A trip made by an earlier attempt that failed to load: a retry joins it
  /// instead of planning another.
  RouteSummary? _plannedTrip;

  /// Set when the server wants a load-out weighment before it loads this
  /// trip: the trip to log it against and how many of each type to weigh.
  String? _weighRouteId;
  Map<String, int> _weighNeeded = const {};

  OrderResponse get _order => widget.order;

  /// An order already on a trip keeps what was reserved for it.
  bool get _onTrip => _order.status != 'confirmed';

  List<RouteSummary> _openTrips(List<RouteSummary> trips) => [
    for (final t in trips)
      if (t.status == 'planned' || t.status == 'loaded') t,
  ];

  RouteSummary? _selectedTrip(List<RouteSummary> trips) {
    if (widget.currentTrip != null) return widget.currentTrip;
    if (_plannedTrip != null) return _plannedTrip;
    if (_tripId == _newTrip) return null;
    for (final t in trips) {
      if (t.id == _tripId) return t;
    }
    return null;
  }

  String _tripLabel(RouteSummary trip, FleetData fleet) {
    final orders = trip.stops.length;
    return '${fleet.driverName(trip.driverId)} · '
        '${fleet.vehicleName(trip.vehicleId)} · '
        '$orders ${orders == 1 ? 'order' : 'orders'}';
  }

  /// [warehouseId] is the godown the sheet is showing, which is the first
  /// active one until the user picks another.
  Future<void> _submit(RouteSummary? existing, String warehouseId) async {
    setState(() {
      _busy = true;
      _error = null;
    });

    final routeApi = ref.read(routeApiProvider);
    var trip = existing;
    if (trip == null) {
      final requested = _order.requestedDate;
      final now = DateTime.now();
      final planned = await routeApi.planRoute(
        branchId: _order.branchId,
        driverId: _driverId!,
        vehicleId: _vehicleId!,
        routeDate: requested.isAfter(now) ? requested : now,
      );
      switch (planned) {
        case FailureResult<RouteSummary>(:final failure):
          return _fail(failure);
        case Success<RouteSummary>(:final value):
          trip = value;
          _plannedTrip = value;
      }
    }

    final dispatched = await routeApi.loadAndDispatch(
      trip.id,
      warehouseId: warehouseId,
      orderIds: _order.status == 'confirmed' ? [_order.id] : const [],
    );
    if (dispatched case FailureResult<RouteSummary>(:final failure)) {
      if (failure.errorCode == 'WEIGHMENT_CHECK_REQUIRED') {
        return _askForWeighment(trip, failure);
      }
      return _fail(failure);
    }
    ref.invalidate(activeTripsProvider(_order.branchId));
    if (mounted) Navigator.of(context).pop(true);
  }

  /// Works out what has to be weighed for [trip] (this order plus the
  /// others waiting on it) and shows the weighment step.
  Future<void> _askForWeighment(RouteSummary trip, Failure failure) async {
    final needed = <String, int>{};
    for (final line in _order.lines) {
      final qty = _onTrip ? line.quantityPending : line.quantityOrdered;
      needed[line.cylinderTypeId] = (needed[line.cylinderTypeId] ?? 0) + qty;
    }
    for (final stop in trip.stops) {
      if (stop.status != 'pending' || stop.orderId == _order.id) continue;
      final other = await ref.read(orderApiProvider).getOrder(stop.orderId);
      if (other case Success<OrderResponse>(:final value)) {
        for (final line in value.lines) {
          needed[line.cylinderTypeId] =
              (needed[line.cylinderTypeId] ?? 0) + line.quantityPending;
        }
      }
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _weighRouteId = trip.id;
      _weighNeeded = needed;
      _error =
          'This agency weighs every cylinder before loading. Log the '
          'checks below, then send the trip out again.';
    });
  }

  /// Why the driver or van list is empty, so the fix is obvious: nobody is
  /// registered, they are in another branch, or they are all out on trips.
  String _fleetGap(
    FleetData fleet, {
    required bool drivers,
    required bool vans,
    required Set<String> busyDrivers,
    required Set<String> busyVehicles,
  }) {
    final parts = <String>[];
    if (drivers) {
      final inBranch = fleet.drivers
          .where((d) => d.branchId == _order.branchId)
          .toList();
      parts.add(
        fleet.drivers.isEmpty
            ? 'No drivers have been added yet.'
            : inBranch.isEmpty
            ? 'No driver is registered in this order\'s branch.'
            : inBranch.any((d) => d.isActive && busyDrivers.contains(d.id))
            ? 'Every active driver here is already on a trip.'
            : 'No driver in this branch is active (on leave or inactive).',
      );
    }
    if (vans) {
      final inBranch = fleet.vehicles
          .where((v) => v.branchId == _order.branchId)
          .toList();
      parts.add(
        fleet.vehicles.isEmpty
            ? 'No vans have been added yet.'
            : inBranch.isEmpty
            ? 'No van is registered in this order\'s branch.'
            : inBranch.any((v) => v.isActive && busyVehicles.contains(v.id))
            ? 'Every active van here is already on a trip.'
            : 'No van in this branch is active (in maintenance or inactive).',
      );
    }
    return parts.join(' ');
  }

  void _fail(Failure failure) {
    if (!mounted) return;
    setState(() {
      _busy = false;
      _error = sendOutErrorMessage(failure.errorCode) ?? failure.message;
    });
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final fleetAsync = ref.watch(fleetProvider);
    final tripsAsync = ref.watch(activeTripsProvider(_order.branchId));
    final names = ref.watch(cylinderNamesProvider).value ?? const {};

    final fleet = fleetAsync.value;
    if (fleetAsync.hasError) {
      return LpgErrorState(
        message: errorMessage(fleetAsync.error!),
        onRetry: () => ref.invalidate(fleetProvider),
      );
    }
    if (fleet == null || tripsAsync.isLoading) {
      return const Padding(
        padding: EdgeInsets.all(LpgSpacing.xl),
        child: Center(child: LpgLoadingIndicator()),
      );
    }

    final trips = tripsAsync.value ?? const <RouteSummary>[];
    final trip = _selectedTrip(trips);
    final isNewTrip = trip == null;

    // A driver or van can only be on one open trip anywhere, so who is busy
    // comes from every branch's trips, not just this order's branch.
    final everyTrip = ref.watch(dispatchTripsProvider).value ?? trips;
    final busyDrivers = {for (final t in everyTrip) t.driverId};
    final busyVehicles = {for (final t in everyTrip) t.vehicleId};
    final drivers = {
      for (final d in fleet.drivers)
        if (d.isActive &&
            d.branchId == _order.branchId &&
            !busyDrivers.contains(d.id))
          d.id: d.name,
    };
    final vehicles = {
      for (final v in fleet.vehicles)
        if (v.isActive &&
            v.branchId == _order.branchId &&
            !busyVehicles.contains(v.id))
          v.id: '${v.registrationNumber} · holds ${v.capacityUnits}',
    };

    final inBranch = [
      for (final w in fleet.warehouses)
        if (w.isActive && w.branchId == _order.branchId) w,
    ];
    final godowns = inBranch.isNotEmpty
        ? inBranch
        : [
            for (final w in fleet.warehouses)
              if (w.isActive) w,
          ];
    final warehouseId =
        _warehouseId ?? (godowns.isEmpty ? null : godowns.first.id);

    final vehicleId = trip?.vehicleId ?? _vehicleId;
    final vanStock = vehicleId == null
        ? const <String, int>{}
        : ref.watch(filledStockProvider(('vehicle', vehicleId))).value ??
              const <String, int>{};
    final godownStockAsync = warehouseId == null
        ? null
        : ref.watch(filledStockProvider(('warehouse', warehouseId)));
    final godownStock = godownStockAsync?.value;

    // The trip is loaded as a whole, so the load sheet counts the other
    // orders waiting on it too, not just this one.
    final companionIds = trip != null && trip.status == 'planned'
        ? [
            for (final s in trip.stops)
              if (s.status == 'pending' && s.orderId != _order.id) s.orderId,
          ]
        : const <String>[];
    final companionNeeds = companionIds.isEmpty
        ? const <String, int>{}
        : ref.watch(tripCompanionNeedsProvider(companionIds.join(','))).value ??
              const <String, int>{};
    final needsByType = <String, int>{
      for (final line in _order.lines)
        line.cylinderTypeId: _onTrip
            ? line.quantityPending
            : line.quantityOrdered,
    };
    companionNeeds.forEach((type, qty) {
      needsByType[type] = (needsByType[type] ?? 0) + qty;
    });
    final rows = [
      for (final entry in needsByType.entries)
        _LoadRow.of(
          name: names[entry.key] ?? 'Cylinder',
          forOrder: entry.value,
          onVan: vanStock[entry.key] ?? 0,
          inGodown: godownStock == null ? null : godownStock[entry.key] ?? 0,
        ),
    ];
    final short = rows.any((r) => r.short);

    final companions = trip != null && trip.status == 'planned'
        ? trip.stops
              .where((s) => s.status == 'pending' && s.orderId != _order.id)
              .length
        : 0;

    final canSubmit =
        !_busy &&
        warehouseId != null &&
        !short &&
        (!isNewTrip || (_driverId != null && _vehicleId != null));

    final tripOptions = <String, String>{
      _newTrip: 'New trip',
      for (final t in _openTrips(trips)) t.id: _tripLabel(t, fleet),
    };

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Load the van with this order and hand it to the driver in one step.',
            style: text.bodyMedium?.copyWith(
              color: context.lpgColors.textSecondary,
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          if (widget.currentTrip != null)
            LpgKeyValueRow(
              label: 'Trip',
              value: _tripLabel(widget.currentTrip!, fleet),
            )
          else ...[
            LpgDropdownField<String>(
              label: 'Trip',
              value: tripOptions.containsKey(_tripId) ? _tripId : _newTrip,
              items: tripOptions,
              onChanged: _busy || _plannedTrip != null
                  ? null
                  : (id) => setState(() => _tripId = id ?? _newTrip),
            ),
            if (isNewTrip) ...[
              const SizedBox(height: LpgSpacing.md),
              LpgDropdownField<String?>(
                label: 'Driver',
                isRequired: true,
                placeholder: drivers.isEmpty
                    ? 'No free driver in this branch'
                    : 'Choose a driver',
                value: drivers.containsKey(_driverId) ? _driverId : null,
                items: drivers,
                onChanged: _busy
                    ? null
                    : (id) => setState(() => _driverId = id),
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgDropdownField<String?>(
                label: 'Van',
                isRequired: true,
                placeholder: vehicles.isEmpty
                    ? 'No free van in this branch'
                    : 'Choose a van',
                value: vehicles.containsKey(_vehicleId) ? _vehicleId : null,
                items: vehicles,
                onChanged: _busy
                    ? null
                    : (id) => setState(() => _vehicleId = id),
              ),
              if (drivers.isEmpty || vehicles.isEmpty) ...[
                const SizedBox(height: LpgSpacing.md),
                _FleetBlockers(
                  message: _fleetGap(
                    fleet,
                    drivers: drivers.isEmpty,
                    vans: vehicles.isEmpty,
                    busyDrivers: busyDrivers,
                    busyVehicles: busyVehicles,
                  ),
                  needDriver: drivers.isEmpty,
                  needVan: vehicles.isEmpty,
                  busyTrips: [
                    for (final t in everyTrip)
                      if ((drivers.isEmpty &&
                              fleet.drivers.any(
                                (d) =>
                                    d.id == t.driverId &&
                                    d.branchId == _order.branchId,
                              )) ||
                          (vehicles.isEmpty &&
                              fleet.vehicles.any(
                                (v) =>
                                    v.id == t.vehicleId &&
                                    v.branchId == _order.branchId,
                              )))
                        t,
                  ],
                  fleet: fleet,
                  hasOpenTrips: _openTrips(trips).isNotEmpty,
                ),
              ],
            ],
          ],
          const SizedBox(height: LpgSpacing.md),
          LpgDropdownField<String?>(
            label: 'Load from godown',
            isRequired: true,
            placeholder: godowns.isEmpty
                ? 'No active godown'
                : 'Choose a godown',
            value: godowns.any((w) => w.id == warehouseId) ? warehouseId : null,
            items: {for (final w in godowns) w.id: w.name},
            onChanged: _busy ? null : (id) => setState(() => _warehouseId = id),
          ),
          const SizedBox(height: LpgSpacing.md),
          Text('Cylinders', style: text.titleSmall),
          const SizedBox(height: LpgSpacing.xs),
          for (final row in rows) _LoadRowTile(row: row),
          if (short) ...[
            const SizedBox(height: LpgSpacing.sm),
            const LpgBanner(
              tone: LpgTone.danger,
              message:
                  "The godown doesn't have enough filled cylinders for this trip. Receive stock or pick another godown.",
            ),
          ],
          if (companions > 0) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(
              message:
                  '$companions other ${companions == 1 ? 'order' : 'orders'} '
                  'on this trip will go out with it.',
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          if (_weighRouteId != null) ...[
            const SizedBox(height: LpgSpacing.md),
            WeighmentSection(
              routeId: _weighRouteId!,
              needed: _weighNeeded,
              names: names,
              warehouseId: warehouseId,
            ),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Load and send out',
            icon: LpgIcons.truck,
            isLoading: _busy,
            expand: true,
            onPressed: canSubmit ? () => _submit(trip, warehouseId) : null,
          ),
        ],
      ),
    );
  }
}

/// One cylinder type against the van and the godown: the server's arithmetic.
class _LoadRow {
  const _LoadRow._({
    required this.name,
    required this.forOrder,
    required this.onVan,
    required this.toLoad,
    required this.inGodown,
    required this.short,
  });

  factory _LoadRow.of({
    required String name,
    required int forOrder,
    required int onVan,
    required int? inGodown,
  }) {
    final toLoad = forOrder > onVan ? forOrder - onVan : 0;
    return _LoadRow._(
      name: name,
      forOrder: forOrder,
      onVan: onVan,
      toLoad: toLoad,
      inGodown: inGodown,
      short: inGodown != null && toLoad > inGodown,
    );
  }

  final String name;
  final int forOrder;
  final int onVan;
  final int toLoad;
  final int? inGodown;
  final bool short;
}

class _LoadRowTile extends StatelessWidget {
  const _LoadRowTile({required this.row});

  final _LoadRow row;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final godown = row.inGodown == null ? '–' : '${row.inGodown}';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(flex: 3, child: Text(row.name, style: text.bodyMedium)),
          Expanded(
            flex: 4,
            child: Text(
              'Needs ${row.forOrder} · on van ${row.onVan} · '
              'load ${row.toLoad} · godown $godown',
              textAlign: TextAlign.right,
              style: text.bodySmall?.copyWith(
                color: row.short ? colors.statusDanger : colors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// What to do when every driver or van is taken: who is holding them, a
/// shortcut to open that trip, and one-tap ways to add a driver or a van.
class _FleetBlockers extends StatelessWidget {
  const _FleetBlockers({
    required this.message,
    required this.needDriver,
    required this.needVan,
    required this.busyTrips,
    required this.fleet,
    required this.hasOpenTrips,
  });

  final String message;
  final bool needDriver;
  final bool needVan;
  final List<RouteSummary> busyTrips;
  final FleetData fleet;
  final bool hasOpenTrips;

  /// Closes the sheet, then opens [open] on the router that outlives it.
  void _go(BuildContext context, void Function(GoRouter router) open) {
    final router = GoRouter.of(context);
    Navigator.of(context).pop();
    open(router);
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgBanner(tone: LpgTone.warning, message: message),
        if (hasOpenTrips) ...[
          const SizedBox(height: LpgSpacing.sm),
          Text(
            'Quickest way: pick an open trip in "Trip" above and this order '
            'joins it.',
            style: text.bodySmall?.copyWith(color: colors.textSecondary),
          ),
        ],
        if (busyTrips.isNotEmpty) ...[
          const SizedBox(height: LpgSpacing.md),
          Text('Who is holding them', style: text.titleSmall),
          const SizedBox(height: LpgSpacing.xs),
          for (final trip in busyTrips)
            Padding(
              padding: const EdgeInsets.only(bottom: LpgSpacing.xs),
              child: LpgListTile(
                title:
                    '${fleet.vehicleName(trip.vehicleId)} · '
                    '${fleet.driverName(trip.driverId)}',
                subtitle:
                    '${tripStatusLabel(trip.status)} · '
                    '${trip.stops.length} '
                    '${trip.stops.length == 1 ? 'stop' : 'stops'}',
                onTap: () => _go(
                  context,
                  (router) => router.pushNamed(
                    'trip_detail',
                    pathParameters: {'tripId': trip.id},
                  ),
                ),
              ),
            ),
        ],
        const SizedBox(height: LpgSpacing.sm),
        Row(
          children: [
            if (needDriver)
              Expanded(
                child: LpgButton(
                  label: 'Add a driver',
                  icon: LpgIcons.add,
                  variant: LpgButtonVariant.secondary,
                  onPressed: () => _go(
                    context,
                    (router) => router.pushNamed('fleet_driver_new'),
                  ),
                ),
              ),
            if (needDriver && needVan) const SizedBox(width: LpgSpacing.sm),
            if (needVan)
              Expanded(
                child: LpgButton(
                  label: 'Add a van',
                  icon: LpgIcons.add,
                  variant: LpgButtonVariant.secondary,
                  onPressed: () => _go(
                    context,
                    (router) => router.pushNamed('fleet_vehicle_new'),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}
