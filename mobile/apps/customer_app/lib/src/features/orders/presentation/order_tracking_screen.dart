import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../../widgets/location_map.dart';
import '../../../widgets/map_tile_provider.dart';
import '../data/order_tracking_provider.dart';
import '../data/orders_provider.dart';

/// A live driver position older than this is shown as paused rather than
/// current — the Driver App sends a ping roughly every 15s.
const _staleAfter = Duration(seconds: 90);

class OrderTrackingScreen extends ConsumerWidget {
  const OrderTrackingScreen({super.key, required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orderAsync = ref.watch(orderDetailProvider(orderId));
    final trackingAsync = ref.watch(orderTrackingProvider(orderId));
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Track Order',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: orderAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Failed to load order tracking: $err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(orderDetailProvider(orderId)),
        ),
        data: (order) {
          final status = order.status;

          return Column(
            children: [
              // Delivery-location map
              Expanded(
                flex: 3,
                child: trackingAsync.when(
                  loading: () => ColoredBox(
                    color: colors.surfaceOverlay,
                    child: const Center(child: LpgLoadingIndicator()),
                  ),
                  error: (_, _) => const MapUnavailable(
                    message: 'The map is unavailable right now.',
                  ),
                  data: (tracking) {
                    if (!tracking.hasLocation) {
                      return const MapUnavailable(
                        message:
                            'A map pin has not been set for this delivery '
                            'address yet. Add one when editing the address.',
                      );
                    }
                    return _TrackingMap(orderId: orderId, tracking: tracking);
                  },
                ),
              ),

              // Order Milestones
              Expanded(
                flex: 4,
                child: Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: colors.surfaceBase,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(32),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.05),
                        blurRadius: 20,
                        offset: const Offset(0, -5),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Order + tracking reference — tap either to copy.
                      Row(
                        children: [
                          Expanded(
                            child: _CopyableRef(
                              label: 'Order',
                              display: order.orderNumber ??
                                  '#${order.id.substring(0, 8).toUpperCase()}',
                              value: order.orderNumber ?? order.id,
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: _CopyableRef(
                              label: 'Tracking ID',
                              display: order.id.substring(0, 8).toUpperCase(),
                              value: order.id,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Divider(height: 1, color: colors.borderDefault),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Order Status',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                              Text(
                                status.replaceAll('_', ' ').toUpperCase(),
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: colors.textPrimary,
                                ),
                              ),
                            ],
                          ),
                          LpgStatusBadge(
                            label: status.replaceAll('_', ' ').toUpperCase(),
                            severity: _getSeverity(status),
                          ),
                        ],
                      ),
                      if (trackingAsync.value?.driver case final driver?) ...[
                        const SizedBox(height: 16),
                        _DriverRow(driver: driver),
                      ],
                      const SizedBox(height: 24),
                      Expanded(
                        child: ListView(
                          children: [
                            _buildMilestone(
                              context,
                              title: 'Order Placed',
                              time: 'Completed',
                              isCompleted: true,
                              isLast: false,
                            ),
                            _buildMilestone(
                              context,
                              title: 'Confirmed by Agency',
                              time: status != 'booked'
                                  ? 'Completed'
                                  : 'Pending',
                              isCompleted: status != 'booked',
                              isLast: false,
                              isCurrent: status == 'confirmed',
                            ),
                            _buildMilestone(
                              context,
                              title: 'Out for Delivery',
                              time:
                                  status == 'out_for_delivery' ||
                                      status == 'delivered'
                                  ? 'In Progress'
                                  : 'Pending',
                              isCompleted:
                                  status == 'out_for_delivery' ||
                                  status == 'delivered',
                              isLast: false,
                              isCurrent: status == 'out_for_delivery',
                            ),
                            _buildMilestone(
                              context,
                              title: 'Delivered',
                              time: status == 'delivered'
                                  ? 'Completed'
                                  : 'Pending',
                              isCompleted: status == 'delivered',
                              isLast: true,
                              isCurrent: status == 'delivered',
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  LpgStatusSeverity _getSeverity(String status) {
    return switch (status) {
      'delivered' => LpgStatusSeverity.success,
      'cancelled' || 'failed_delivery' => LpgStatusSeverity.danger,
      'out_for_delivery' || 'ready_for_dispatch' => LpgStatusSeverity.warning,
      _ => LpgStatusSeverity.info,
    };
  }

  Widget _buildMilestone(
    BuildContext context, {
    required String title,
    required String time,
    required bool isCompleted,
    required bool isLast,
    bool isCurrent = false,
  }) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return IntrinsicHeight(
      child: Row(
        children: [
          Column(
            children: [
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: colors.surfaceRaised,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isCompleted
                        ? colors.actionPrimary
                        : colors.borderDefault,
                  ),
                ),
                child: Center(
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: isCompleted
                          ? colors.actionPrimary
                          : colors.borderStrong,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    color: isCompleted
                        ? colors.actionPrimary
                        : colors.borderDefault,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: isCurrent
                          ? FontWeight.bold
                          : FontWeight.normal,
                      color: isCompleted
                          ? colors.textPrimary
                          : colors.textSecondary,
                    ),
                  ),
                  Text(
                    time,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The tracking map: the delivery destination pin plus the driver's live
/// marker, once the route is in progress and the Driver App is sharing.
class _TrackingMap extends ConsumerStatefulWidget {
  const _TrackingMap({required this.orderId, required this.tracking});

  final String orderId;
  final OrderTrackingView tracking;

  @override
  ConsumerState<_TrackingMap> createState() => _TrackingMapState();
}

class _TrackingMapState extends ConsumerState<_TrackingMap> {
  final _mapController = MapController();
  Timer? _stalenessTicker;

  @override
  void initState() {
    super.initState();
    // Surface "paused" when pings stop arriving — nothing else rebuilds this
    // widget once the stream goes quiet.
    _stalenessTicker = Timer.periodic(
      const Duration(seconds: 30),
      (_) => setState(() {}),
    );
  }

  @override
  void dispose() {
    _stalenessTicker?.cancel();
    _mapController.dispose();
    super.dispose();
  }

  void _recenter(LatLng destination, LatLng? driver) {
    if (driver == null) {
      _mapController.move(destination, 15);
      return;
    }
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: LatLngBounds(destination, driver),
        padding: const EdgeInsets.all(56),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final destination = widget.tracking.destination!;
    final driverAsync = ref.watch(driverLocationProvider(widget.orderId));
    final driver = driverAsync.value;

    final isStale =
        driver != null &&
        DateTime.now().difference(driver.at) > _staleAfter;

    return Stack(
      children: [
        Positioned.fill(
          child: LocationMap(
            mapController: _mapController,
            center: destination,
            interactive: true,
            tileProvider: ref.watch(mapTileProviderProvider),
            markers: [
              pinMarker(point: destination, color: colors.actionPrimary),
              if (driver != null)
                driverMarker(
                  point: driver.point,
                  color: isStale ? colors.textSecondary : colors.statusInfo,
                ),
            ],
          ),
        ),
        if (widget.tracking.destinationIsApproximate)
          const Positioned(
            top: 12,
            left: 12,
            right: 12,
            child: _ApproximateBanner(),
          ),
        Positioned(
          right: 12,
          bottom: 12,
          child: FloatingActionButton.small(
            heroTag: 'tracking-recenter',
            onPressed: () => _recenter(destination, driver?.point),
            child: const Icon(Icons.center_focus_strong),
          ),
        ),
        if (widget.tracking.isRouteActive)
          Positioned(
            left: 12,
            bottom: 12,
            child: _DriverStatusChip(
              driverPresent: driver != null,
              stale: isStale,
            ),
          ),
      ],
    );
  }
}

class _DriverStatusChip extends StatelessWidget {
  const _DriverStatusChip({required this.driverPresent, required this.stale});

  final bool driverPresent;
  final bool stale;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    final (label, icon, color) = switch ((driverPresent, stale)) {
      (false, _) => (
        "Waiting for the driver's location",
        Icons.location_searching,
        colors.textSecondary,
      ),
      (true, true) => (
        'Live location paused',
        Icons.pause_circle_outline,
        colors.statusWarning,
      ),
      (true, false) => (
        'Driver en route',
        Icons.local_shipping,
        colors.statusInfo,
      ),
    };

    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.surfaceBase.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: colors.borderDefault),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 8),
            Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.textPrimary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Shown over the map when the pin was derived from geocoding the address
/// text rather than a location the customer set themselves.
class _ApproximateBanner extends StatelessWidget {
  const _ApproximateBanner();

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.surfaceBase.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.borderDefault),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.info_outline, size: 16, color: colors.textSecondary),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                'Approximate location, based on the delivery address.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The assigned-driver line under the order status. Tap it to open the
/// driver details sheet.
class _DriverRow extends StatelessWidget {
  const _DriverRow({required this.driver});

  final TrackingDriver driver;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final vehicle = [
      driver.vehicleModel,
      driver.vehicleNumber,
    ].where((s) => s != null && s.isNotEmpty).join(' · ');

    return InkWell(
      onTap: () => showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        builder: (_) => _DriverSheet(driver: driver),
      ),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: colors.surfaceOverlay,
              child: Icon(
                Icons.person_outline,
                size: 20,
                color: colors.textSecondary,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Your driver',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  Text(
                    driver.name,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: colors.textPrimary,
                    ),
                  ),
                  if (vehicle.isNotEmpty)
                    Text(
                      vehicle,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: colors.textSecondary),
          ],
        ),
      ),
    );
  }
}

class _DriverSheet extends StatelessWidget {
  const _DriverSheet({required this.driver});

  final TrackingDriver driver;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: colors.actionPrimary,
                  child: Text(
                    driver.name.isNotEmpty ? driver.name[0].toUpperCase() : '?',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: colors.textInverse,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Text(
                    driver.name,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: colors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            if ((driver.vehicleNumber ?? '').isNotEmpty)
              _DriverDetailTile(
                icon: Icons.local_shipping_outlined,
                label: 'Vehicle',
                value: [driver.vehicleModel, driver.vehicleNumber]
                    .where((s) => s != null && s.isNotEmpty)
                    .join(' · '),
              ),
            if ((driver.phoneNumber ?? '').isNotEmpty)
              _DriverDetailTile(
                icon: Icons.phone_outlined,
                label: 'Phone',
                value: driver.phoneNumber!,
                onCopy: driver.phoneNumber!,
              ),
          ],
        ),
      ),
    );
  }
}

class _DriverDetailTile extends StatelessWidget {
  const _DriverDetailTile({
    required this.icon,
    required this.label,
    required this.value,
    this.onCopy,
  });

  final IconData icon;
  final String label;
  final String value;

  /// When set, the tile is tappable and copies this to the clipboard.
  final String? onCopy;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    Future<void> copy() async {
      await Clipboard.setData(ClipboardData(text: onCopy!));
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text('$label copied'),
            duration: const Duration(seconds: 1),
          ),
        );
    }

    return InkWell(
      onTap: onCopy == null ? null : copy,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            Icon(icon, size: 20, color: colors.textSecondary),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  Text(
                    value,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colors.textPrimary,
                    ),
                  ),
                ],
              ),
            ),
            if (onCopy != null)
              Icon(Icons.copy_rounded, size: 16, color: colors.textSecondary),
          ],
        ),
      ),
    );
  }
}

/// A labelled reference (order number, tracking id) that copies its full
/// value to the clipboard when tapped.
class _CopyableRef extends StatelessWidget {
  const _CopyableRef({
    required this.label,
    required this.display,
    required this.value,
  });

  /// Caption above the value, e.g. "Order" / "Tracking ID".
  final String label;

  /// What's shown — may be shortened for display.
  final String display;

  /// The full string put on the clipboard.
  final String value;

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text('$label copied'),
          duration: const Duration(seconds: 1),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    return InkWell(
      onTap: () => _copy(context),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: theme.textTheme.labelSmall?.copyWith(
                color: colors.textSecondary,
              ),
            ),
            const SizedBox(height: 2),
            Row(
              children: [
                Flexible(
                  child: Text(
                    display,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: colors.textPrimary,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Icon(Icons.copy_rounded, size: 14, color: colors.textSecondary),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
