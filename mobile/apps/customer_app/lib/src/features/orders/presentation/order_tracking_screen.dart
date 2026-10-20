import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maps/maps.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/order_tracking_provider.dart';
import '../data/orders_provider.dart';
import 'order_presentation.dart';

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
    final colors = context.lpgColors;

    return Scaffold(
      appBar: AppBar(title: const Text('Track Order')),
      body: orderAsync.when(
        loading: () => const LpgLoadingIndicator(),
        error: (err, _) => LpgErrorState(
          message: 'Failed to load order tracking: $err',
          onRetry: () => ref.refresh(orderDetailProvider(orderId)),
        ),
        data: (order) {
          return Column(
            children: [
              // Delivery-location map
              Expanded(
                flex: 3,
                child: trackingAsync.when(
                  loading: () => ColoredBox(
                    color: colors.surfaceOverlay,
                    child: const LpgLoadingIndicator(),
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

              // Order details and milestones, on a sheet that overlaps the
              // bottom of the map.
              Expanded(
                flex: 4,
                child: Container(
                  decoration: BoxDecoration(
                    color: colors.card,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(LpgRadius.xxl),
                    ),
                    border: colors.isHighContrast
                        ? Border(
                            top: BorderSide(
                              color: colors.borderStrong,
                              width: 2,
                            ),
                          )
                        : null,
                    boxShadow: colors.floatingShadow,
                  ),
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(
                      LpgSpacing.mdl,
                      LpgSpacing.lg,
                      LpgSpacing.mdl,
                      LpgSpacing.lg,
                    ),
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Order Status',
                                  style: context.lpgText.labelMedium,
                                ),
                                const SizedBox(height: LpgSpacing.xs / 2),
                                Text(
                                  LpgFormat.sentence(order.status),
                                  style: context.lpgText.titleLarge,
                                ),
                              ],
                            ),
                          ),
                          LpgStatusBadge(
                            label: order.statusLabel,
                            severity: order.statusSeverity,
                          ),
                        ],
                      ),
                      const SizedBox(height: LpgSpacing.md),
                      // Order + tracking reference — tap either to copy.
                      Row(
                        children: [
                          Expanded(
                            child: _CopyableRef(
                              label: 'Order',
                              display: LpgFormat.orderNumber(
                                order.orderNumber,
                                order.id,
                              ),
                              value: order.orderNumber ?? order.id,
                            ),
                          ),
                          const SizedBox(width: LpgSpacing.sm),
                          Expanded(
                            child: _CopyableRef(
                              label: 'Tracking ID',
                              display: order.id.substring(0, 8).toUpperCase(),
                              value: order.id,
                            ),
                          ),
                        ],
                      ),
                      if (trackingAsync.value?.driver case final driver?) ...[
                        const SizedBox(height: LpgSpacing.md),
                        _DriverRow(driver: driver),
                      ],
                      const SizedBox(height: LpgSpacing.lg),
                      LpgTimeline(steps: _milestones(order.status)),
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

  /// The four customer-facing milestones, with the step the order has
  /// reached marked current (or failed, for a cancelled/failed order).
  static List<LpgTimelineStep> _milestones(String status) {
    const titles = [
      'Order Placed',
      'Confirmed by Agency',
      'Out for Delivery',
      'Delivered',
    ];
    final reached = switch (status) {
      'booked' => 0,
      'out_for_delivery' || 'failed_delivery' => 2,
      'delivered' => 3,
      _ => 1,
    };
    final failed = status == 'cancelled' || status == 'failed_delivery';

    return [
      for (var i = 0; i < titles.length; i++)
        () {
          final LpgTimelineState state;
          if (i < reached || status == 'delivered') {
            state = LpgTimelineState.done;
          } else if (i == reached) {
            state = failed ? LpgTimelineState.failed : LpgTimelineState.current;
          } else {
            state = LpgTimelineState.upcoming;
          }
          return LpgTimelineStep(
            title: titles[i],
            state: state,
            subtitle: switch (state) {
              LpgTimelineState.done => 'Completed',
              LpgTimelineState.current => 'In Progress',
              LpgTimelineState.upcoming => 'Pending',
              LpgTimelineState.failed => LpgFormat.sentence(status),
            },
          );
        }(),
    ];
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
        padding: const EdgeInsets.all(LpgSpacing.xxl + LpgSpacing.sm),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final destination = widget.tracking.destination!;
    final driverAsync = ref.watch(driverLocationProvider(widget.orderId));
    final driver = driverAsync.value;

    final isStale =
        driver != null && DateTime.now().difference(driver.at) > _staleAfter;

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
            top: LpgSpacing.smd,
            left: LpgSpacing.smd,
            right: LpgSpacing.smd,
            child: _ApproximateBanner(),
          ),
        Positioned(
          right: LpgSpacing.smd,
          bottom: LpgSpacing.lg,
          child: FloatingActionButton.small(
            heroTag: 'tracking-recenter',
            tooltip: 'Recenter map',
            onPressed: () => _recenter(destination, driver?.point),
            child: const Icon(LpgIcons.recenter),
          ),
        ),
        if (widget.tracking.isRouteActive)
          Positioned(
            left: LpgSpacing.smd,
            bottom: LpgSpacing.lg,
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
    final colors = context.lpgColors;

    final (label, icon, color) = switch ((driverPresent, stale)) {
      (false, _) => (
        "Waiting for the driver's location",
        LpgIcons.locating,
        colors.textSecondary,
      ),
      (true, true) => (
        'Live location paused',
        LpgIcons.paused,
        colors.statusWarning,
      ),
      (true, false) => ('Driver en route', LpgIcons.truck, colors.statusInfo),
    };

    return _MapOverlay(
      shape: const StadiumBorder(),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: LpgSizes.iconSm, color: color),
          const SizedBox(width: LpgSpacing.sm),
          Text(
            label,
            style: context.lpgText.labelMedium?.copyWith(
              color: colors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

/// A frosted card floating over the map, so overlays stay legible on any
/// tile colour.
class _MapOverlay extends StatelessWidget {
  const _MapOverlay({required this.child, required this.shape});

  final Widget child;
  final ShapeBorder shape;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return DecoratedBox(
      decoration: ShapeDecoration(
        color: colors.card.withValues(alpha: colors.isHighContrast ? 1 : 0.94),
        shape: shape is StadiumBorder
            ? StadiumBorder(side: BorderSide(color: colors.borderDefault))
            : RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(LpgRadius.lg),
                side: BorderSide(color: colors.borderDefault),
              ),
        shadows: colors.cardShadow,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: LpgSpacing.smd,
          vertical: LpgSpacing.sm,
        ),
        child: child,
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
    final colors = context.lpgColors;
    return _MapOverlay(
      shape: const RoundedRectangleBorder(),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(LpgIcons.info, size: LpgSizes.iconSm, color: colors.statusInfo),
          const SizedBox(width: LpgSpacing.sm),
          Flexible(
            child: Text(
              'Approximate location, based on the delivery address.',
              style: context.lpgText.bodySmall?.copyWith(
                color: colors.textPrimary,
              ),
            ),
          ),
        ],
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
    final vehicle = [
      driver.vehicleModel,
      driver.vehicleNumber,
    ].where((s) => s != null && s.isNotEmpty).join(' · ');

    return LpgCard(
      variant: LpgCardVariant.outlined,
      padding: EdgeInsets.zero,
      child: LpgListTile(
        leading: LpgAvatar(name: driver.name, size: LpgSizes.iconBox),
        title: driver.name,
        subtitle: vehicle.isNotEmpty ? 'Your driver · $vehicle' : 'Your driver',
        showChevron: true,
        onTap: () => LpgFeedback.showSheet<void>(
          context,
          builder: (_) => _DriverSheet(driver: driver),
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
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            LpgAvatar(name: driver.name),
            const SizedBox(width: LpgSpacing.md),
            Expanded(
              child: Text(driver.name, style: context.lpgText.titleLarge),
            ),
          ],
        ),
        const SizedBox(height: LpgSpacing.mdl),
        if ((driver.vehicleNumber ?? '').isNotEmpty)
          _DriverDetailTile(
            icon: LpgIcons.truck,
            label: 'Vehicle',
            value: [
              driver.vehicleModel,
              driver.vehicleNumber,
            ].where((s) => s != null && s.isNotEmpty).join(' · '),
          ),
        if ((driver.phoneNumber ?? '').isNotEmpty)
          _DriverPhoneTile(phone: driver.phoneNumber!),
      ],
    );
  }
}

/// The driver's phone row in the details sheet — dial it or copy it.
class _DriverPhoneTile extends StatelessWidget {
  const _DriverPhoneTile({required this.phone});

  final String phone;

  Future<void> _call(BuildContext context) async {
    final dialable = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final launched = await launchUrl(Uri(scheme: 'tel', path: dialable));
    if (!launched && context.mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(content: Text('Could not open the dialer')),
        );
    }
  }

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: phone));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('Phone copied'),
          duration: Duration(seconds: 1),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.sm),
      child: Row(
        children: [
          const LpgIconBox(icon: LpgIcons.phone, tone: LpgTone.neutral),
          const SizedBox(width: LpgSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Phone', style: context.lpgText.labelMedium),
                Text(
                  phone,
                  overflow: TextOverflow.ellipsis,
                  style: context.lpgText.bodyLarge,
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: () => _copy(context),
            icon: const Icon(LpgIcons.copy, size: LpgSizes.iconMd),
            tooltip: 'Copy',
            color: context.lpgColors.textSecondary,
          ),
          const SizedBox(width: LpgSpacing.xs),
          LpgButton(
            label: 'Call',
            icon: LpgIcons.call,
            variant: LpgButtonVariant.tonal,
            onPressed: () => _call(context),
          ),
        ],
      ),
    );
  }
}

class _DriverDetailTile extends StatelessWidget {
  const _DriverDetailTile({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.sm),
      child: Row(
        children: [
          LpgIconBox(icon: icon, tone: LpgTone.neutral),
          const SizedBox(width: LpgSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: context.lpgText.labelMedium),
                Text(value, style: context.lpgText.bodyLarge),
              ],
            ),
          ),
        ],
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
    final colors = context.lpgColors;
    return Semantics(
      button: true,
      label: '$label $display, tap to copy',
      excludeSemantics: true,
      child: Material(
        color: colors.surfaceOverlay,
        borderRadius: BorderRadius.circular(LpgRadius.lg),
        child: InkWell(
          onTap: () => _copy(context),
          borderRadius: BorderRadius.circular(LpgRadius.lg),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: LpgSpacing.smd,
              vertical: LpgSpacing.sm,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: context.lpgText.labelMedium),
                const SizedBox(height: LpgSpacing.xs / 2),
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        display,
                        overflow: TextOverflow.ellipsis,
                        style: context.lpgText.titleSmall,
                      ),
                    ),
                    const SizedBox(width: LpgSpacing.xs + 2),
                    Icon(
                      LpgIcons.copy,
                      size: LpgSizes.iconSm - 2,
                      color: colors.textSecondary,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
