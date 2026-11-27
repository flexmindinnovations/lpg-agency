import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

/// LocationIQ API key, supplied at build/run time — never commit a real key.
/// `flutter run --dart-define=LOCATIONIQ_API_KEY=...`, or
/// `--dart-define-from-file=dart_defines.local.json` (gitignored — see each
/// app's `dart_defines.local.json.example`). Empty by default:
/// [GeocodingService] then falls back to calling Nominatim directly, so
/// geocoding still works (just rate-limited) for anyone building without a key.
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
/// traffic. Both responses share the same JSON shape, so only the request
/// side branches. What the service answered, found or not, is cached per query
/// string for the lifetime of the provider so reopening a screen doesn't re-hit
/// it. A failed request (offline, rate limit, server error) is not cached.
class GeocodingService {
  GeocodingService({
    http.Client? client,
    this.apiKey = _locationIqApiKey,
    Future<void> Function(Duration)? pause,
  }) : _client = client ?? http.Client(),
       _pause = pause ?? Future<void>.delayed;

  final http.Client _client;
  final String apiKey;
  final Future<void> Function(Duration) _pause;
  final Map<String, LatLng?> _cache = {};

  /// The gap between two requests that keeps within the free rate limits:
  /// LocationIQ allows two a second, Nominatim one.
  Duration get requestSpacing =>
      Duration(milliseconds: apiKey.isNotEmpty ? 600 : 1100);

  static final Uri _locationIqBase = Uri.parse(
    'https://us1.locationiq.com/v1/search',
  );
  static final Uri _nominatimBase = Uri.parse(
    'https://nominatim.openstreetmap.org/search',
  );

  /// Finds a delivery address. A full street address often matches nothing, so
  /// wider forms of it are tried in turn ([addressQueries]). Stops at the first
  /// match, or when a request fails.
  Future<LatLng?> locate(String address) async {
    var requested = false;
    for (final query in addressQueries(address)) {
      if (_cache.containsKey(query)) {
        final cached = _cache[query];
        if (cached != null) return cached;
        continue;
      }
      if (requested) await _pause(requestSpacing);
      requested = true;
      final point = await search(query);
      if (point != null) return point;
      // Not cached means the request failed: wider forms would fail too.
      if (!_cache.containsKey(query)) return null;
    }
    return null;
  }

  /// The forms of a one-line address to look up, narrowest first: the whole
  /// line, its last four parts, its last three, then its PIN code. Parts that
  /// repeat (a city that is also the district) are dropped.
  static List<String> addressQueries(String address) {
    final seen = <String>{};
    final parts = [
      for (final part in address.split(','))
        if (part.trim().isNotEmpty && seen.add(part.trim().toLowerCase()))
          part.trim(),
    ];
    if (parts.isEmpty) return const [];
    String last(int count) => parts.sublist(parts.length - count).join(', ');
    final pin = RegExp(r'\b[1-9]\d{5}\b').allMatches(address).lastOrNull?[0];
    return {
      parts.join(', '),
      if (parts.length > 4) last(4),
      if (parts.length > 3) last(3),
      if (pin != null) '$pin, India',
    }.toList();
  }

  Future<LatLng?> search(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return null;
    if (_cache.containsKey(trimmed)) return _cache[trimmed];

    try {
      final res =
          await (apiKey.isNotEmpty
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
                        queryParameters: {
                          'q': trimmed,
                          'format': 'jsonv2',
                          'limit': '1',
                        },
                      ),
                      headers: const {
                        'User-Agent': 'lpg-agency/1.0 (delivery tracking)',
                      },
                    ))
              .timeout(const Duration(seconds: 8));

      // LocationIQ answers 404 when it finds nothing.
      if (res.statusCode == 404) return _cache[trimmed] = null;
      if (res.statusCode != 200) return null;

      final body = jsonDecode(res.body);
      if (body is! List || body.isEmpty) return _cache[trimmed] = null;

      final first = body.first as Map<String, dynamic>;
      final lat = double.tryParse('${first['lat']}');
      final lon = double.tryParse('${first['lon']}');
      if (lat == null || lon == null) return _cache[trimmed] = null;

      return _cache[trimmed] = LatLng(lat, lon);
    } catch (_) {
      return null;
    }
  }

  void dispose() => _client.close();
}

final geocodingServiceProvider = Provider<GeocodingService>((ref) {
  final service = GeocodingService();
  ref.onDispose(service.dispose);
  return service;
});
