import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:maps/maps.dart';

/// Roughly the geographic centre of India — the picker's starting view when
/// there's no existing pin and the device location isn't available.
const _defaultCenter = LatLng(20.5937, 78.9629);

/// A form control for pinning an address on a map. Optional — a delivery
/// still works without coordinates, they just make the customer's
/// order-tracking map accurate.
class LocationPickerField extends StatelessWidget {
  const LocationPickerField({
    super.key,
    required this.value,
    required this.onChanged,
    this.tileProvider,
  });

  final LatLng? value;
  final ValueChanged<LatLng?> onChanged;
  final TileProvider? tileProvider;

  Future<void> _openPicker(BuildContext context) async {
    final picked = await Navigator.of(context).push<LatLng>(
      MaterialPageRoute(
        builder: (_) =>
            _LocationPickerScreen(initial: value, tileProvider: tileProvider),
        fullscreenDialog: true,
      ),
    );
    if (picked != null) onChanged(picked);
  }

  static const _previewHeight = 140.0;
  static const _pinnedZoom = 16.0;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final pinned = value;

    if (pinned == null) {
      return LpgButton(
        label: 'Pin location on map (optional)',
        icon: LpgIcons.addLocation,
        variant: LpgButtonVariant.secondary,
        expand: true,
        onPressed: () => _openPicker(context),
      );
    }

    return LpgCard(
      variant: LpgCardVariant.outlined,
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(LpgRadius.xl),
            ),
            child: SizedBox(
              height: _previewHeight,
              child: LocationMap(
                key: ValueKey(pinned),
                center: pinned,
                zoom: _pinnedZoom,
                tileProvider: tileProvider,
                markers: [
                  pinMarker(point: pinned, color: colors.actionPrimary),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(left: LpgSpacing.smd),
            child: Row(
              children: [
                Icon(
                  LpgIcons.successFilled,
                  size: LpgSizes.iconSm,
                  color: colors.statusSuccess,
                ),
                const SizedBox(width: LpgSpacing.sm),
                Text('Location pinned', style: context.lpgText.bodySmall),
                const Spacer(),
                TextButton(
                  onPressed: () => _openPicker(context),
                  child: const Text('Change'),
                ),
                TextButton(
                  onPressed: () => onChanged(null),
                  child: const Text('Remove'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LocationPickerScreen extends StatefulWidget {
  const _LocationPickerScreen({this.initial, this.tileProvider});

  final LatLng? initial;
  final TileProvider? tileProvider;

  @override
  State<_LocationPickerScreen> createState() => _LocationPickerScreenState();
}

class _LocationPickerScreenState extends State<_LocationPickerScreen> {
  final _mapController = MapController();
  LatLng? _pin;
  bool _locating = false;

  @override
  void initState() {
    super.initState();
    _pin = widget.initial;
  }

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  Future<void> _useCurrentLocation() async {
    setState(() => _locating = true);
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        _snack('Turn on location services to use this.');
        return;
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        _snack('Location permission is needed to find where you are.');
        return;
      }
      final pos = await Geolocator.getCurrentPosition();
      final here = LatLng(pos.latitude, pos.longitude);
      setState(() => _pin = here);
      _mapController.move(here, LocationPickerField._pinnedZoom);
    } catch (_) {
      _snack('Could not get your current location.');
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  void _snack(String message) {
    if (!mounted) return;
    LpgFeedback.showToast(context, message, tone: LpgTone.warning);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final pin = _pin;

    return Scaffold(
      appBar: AppBar(title: const Text('Pin delivery location')),
      body: Column(
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(
              LpgSpacing.md,
              LpgSpacing.sm,
              LpgSpacing.md,
              LpgSpacing.smd,
            ),
            child: LpgBanner(
              icon: LpgIcons.location,
              message: 'Tap the map to drop a pin on your building entrance.',
            ),
          ),
          Expanded(
            child: LocationMap(
              mapController: _mapController,
              center: pin ?? widget.initial ?? _defaultCenter,
              zoom: pin != null ? LocationPickerField._pinnedZoom : 4,
              interactive: true,
              tileProvider: widget.tileProvider,
              onTap: (point) => setState(() => _pin = point),
              markers: [
                if (pin != null)
                  pinMarker(point: pin, color: colors.actionPrimary),
              ],
            ),
          ),
          DecoratedBox(
            decoration: BoxDecoration(
              color: colors.card,
              border: Border(top: BorderSide(color: colors.borderDefault)),
            ),
            child: SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(LpgSpacing.md),
                child: Column(
                  children: [
                    LpgButton(
                      label: 'Use my current location',
                      icon: LpgIcons.myLocation,
                      variant: LpgButtonVariant.secondary,
                      isLoading: _locating,
                      expand: true,
                      onPressed: _useCurrentLocation,
                    ),
                    const SizedBox(height: LpgSpacing.sm),
                    LpgButton(
                      label: 'Confirm location',
                      icon: LpgIcons.check,
                      expand: true,
                      onPressed: pin == null
                          ? null
                          : () => Navigator.of(context).pop(pin),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
