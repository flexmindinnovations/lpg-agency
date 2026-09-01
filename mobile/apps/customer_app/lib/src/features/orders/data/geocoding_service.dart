import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

/// LocationIQ API key, supplied at build/run time — never commit a real key.
/// `flutter run --dart-define=LOCATIONIQ_API_KEY=...`, or
/// `--dart-define-from-file=dart_defines.local.json` (gitignored — see
/// `dart_defines.local.json.example`). Empty by default: [GeocodingService]
/// then falls back to calling Nominatim directly, so geocoding still works
/// (just rate-limited) for anyone building without a key.
const _locationIqApiKey = String.fromEnvironment('LOCATIONIQ_API_KEY');

/// Forward geocoding for delivery-address strings that were saved before the
/// address form captured a map pin.
///
/// Backed by [LocationIQ](https://locationiq.com) — a hosted,
/// Nominatim-compatible endpoint — whenever a `LOCATIONIQ_API_KEY` is
/// supplied (free tier: 5,000 requests/day, no card required). Without a key
/// it falls back to calling OpenStreetMap's own Nominatim directly, which
/// caps callers at ~1 request/second and requires an identifying
/// `User-Agent`; fine for low-volume dev/demo use, not for production
/// traffic — this is why Step E existed. Both responses share the same JSON
/// shape, so only the request side branches. Results are cached per query
/// string for the lifetime of the provider so reopening a screen doesn't
/// re-hit the service.
class GeocodingService {
  GeocodingService({http.Client? client, this.apiKey = _locationIqApiKey})
    : _client = client ?? http.Client();

  final http.Client _client;
  final String apiKey;
  final Map<String, LatLng?> _cache = {};

  static final Uri _locationIqBase = Uri.parse(
    'https://us1.locationiq.com/v1/search',
  );
  static final Uri _nominatimBase = Uri.parse(
    'https://nominatim.openstreetmap.org/search',
  );

  Future<LatLng?> search(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return null;
    if (_cache.containsKey(trimmed)) return _cache[trimmed];

    try {
      final res = await (apiKey.isNotEmpty
          ? _client.get(
              _locationIqBase.replace(
                queryParameters: {
                  'key': apiKey,
                  'q': trimmed,
                  'format': 'json',
                  'limit': '1',
                },
              ),
            )
          : _client.get(
              _nominatimBase.replace(
                queryParameters: {'q': trimmed, 'format': 'jsonv2', 'limit': '1'},
              ),
              headers: const {
                'User-Agent': 'lpg-agency-customer-app/1.0 (delivery tracking)',
              },
            )).timeout(const Duration(seconds: 8));

      if (res.statusCode != 200) return _cache[trimmed] = null;

      final body = jsonDecode(res.body);
      if (body is! List || body.isEmpty) return _cache[trimmed] = null;

      final first = body.first as Map<String, dynamic>;
      final lat = double.tryParse('${first['lat']}');
      final lon = double.tryParse('${first['lon']}');
      if (lat == null || lon == null) return _cache[trimmed] = null;

      return _cache[trimmed] = LatLng(lat, lon);
    } catch (_) {
      return _cache[trimmed] = null;
    }
  }

  void dispose() => _client.close();
}

final geocodingServiceProvider = Provider<GeocodingService>((ref) {
  final service = GeocodingService();
  ref.onDispose(service.dispose);
  return service;
});
