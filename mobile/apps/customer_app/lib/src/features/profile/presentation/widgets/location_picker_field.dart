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

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    if (value == null) {
      return OutlinedButton.icon(
        onPressed: () => _openPicker(context),
        icon: const Icon(Icons.add_location_alt_outlined),
        label: const Text('Pin location on map (optional)'),
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          side: BorderSide(color: colors.borderDefault),
          foregroundColor: colors.textPrimary,
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox(
            height: 140,
            child: LocationMap(
              key: ValueKey(value),
              center: value!,
              zoom: 16,
              tileProvider: tileProvider,
              markers: [pinMarker(point: value!, color: colors.actionPrimary)],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Icon(Icons.check_circle, size: 16, color: colors.statusSuccess),
            const SizedBox(width: 6),
            Text(
              'Location pinned',
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.textSecondary,
              ),
            ),
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
      ],
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
      _mapController.move(here, 16);
    } catch (_) {
      _snack('Could not get your current location.');
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  void _snack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Pin delivery location',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Text(
              'Tap the map to drop a pin on your building entrance.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.textSecondary,
              ),
            ),
          ),
          Expanded(
            child: LocationMap(
              mapController: _mapController,
              center: _pin ?? widget.initial ?? _defaultCenter,
              zoom: _pin != null ? 16 : 4,
              interactive: true,
              tileProvider: widget.tileProvider,
              onTap: (point) => setState(() => _pin = point),
              markers: [
                if (_pin != null)
                  pinMarker(point: _pin!, color: colors.actionPrimary),
              ],
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  OutlinedButton.icon(
                    onPressed: _locating ? null : _useCurrentLocation,
                    icon: _locating
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.my_location),
                    label: const Text('Use my current location'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(48),
                    ),
                  ),
                  const SizedBox(height: 8),
                  LpgButton(
                    label: 'Confirm location',
                    expand: true,
                    onPressed: _pin == null
                        ? null
                        : () => Navigator.of(context).pop(_pin),
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
