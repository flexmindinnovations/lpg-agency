import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

/// Best-effort forward geocoding for delivery-address strings that were saved
/// before the address form captured a map pin.
///
/// Uses OpenStreetMap's Nominatim (no API key). Nominatim's usage policy caps
/// callers at ~1 request/second and requires an identifying `User-Agent`; this
/// is fine for the low volume of "open the tracking screen for one order" but
/// should move to a paid geocoder before any bulk use. Results are cached per
/// query string for the lifetime of the provider so reopening a screen doesn't
/// re-hit the service.
class GeocodingService {
  GeocodingService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  final Map<String, LatLng?> _cache = {};

  static final Uri _base = Uri.parse('https://nominatim.openstreetmap.org/search');

  Future<LatLng?> search(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return null;
    if (_cache.containsKey(trimmed)) return _cache[trimmed];

    try {
      final uri = _base.replace(
        queryParameters: {'q': trimmed, 'format': 'jsonv2', 'limit': '1'},
      );
      final res = await _client.get(
        uri,
        headers: const {
          'User-Agent': 'lpg-agency-customer-app/1.0 (delivery tracking)',
        },
      ).timeout(const Duration(seconds: 8));

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
