import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:maps/maps.dart';

http.Response _hit(List<Map<String, String>> results) =>
    http.Response(jsonEncode(results), 200);

void main() {
  group('GeocodingService', () {
    test(
      'uses LocationIQ (with the key) when an API key is configured',
      () async {
        final requested = <Uri>[];
        final client = MockClient((req) async {
          requested.add(req.url);
          return _hit([
            {'lat': '17.3850', 'lon': '78.4867'},
          ]);
        });
        final service = GeocodingService(client: client, apiKey: 'pk.test-key');

        final result = await service.search('Hitech City, Hyderabad');

        expect(result, LatLng(17.3850, 78.4867));
        expect(requested.single.host, 'us1.locationiq.com');
        expect(requested.single.queryParameters['key'], 'pk.test-key');
        expect(requested.single.queryParameters['q'], 'Hitech City, Hyderabad');
      },
    );

    test('falls back to Nominatim when no API key is configured', () async {
      final requested = <http.Request>[];
      final client = MockClient((req) async {
        requested.add(req);
        return _hit([
          {'lat': '9.9312', 'lon': '76.2673'},
        ]);
      });
      final service = GeocodingService(client: client, apiKey: '');

      final result = await service.search('Fort Kochi');

      expect(result, LatLng(9.9312, 76.2673));
      expect(requested.single.url.host, 'nominatim.openstreetmap.org');
      expect(requested.single.headers['User-Agent'], contains('lpg-agency'));
    });

    test(
      'caches per query string — a repeat lookup does not re-hit the API',
      () async {
        var calls = 0;
        final client = MockClient((req) async {
          calls++;
          return _hit([
            {'lat': '19.0760', 'lon': '72.8777'},
          ]);
        });
        final service = GeocodingService(client: client, apiKey: 'pk.k');

        await service.search('Mumbai');
        await service.search('Mumbai');

        expect(calls, 1);
      },
    );

    test('returns null on a non-200 or empty result', () async {
      final service = GeocodingService(
        client: MockClient((req) async => http.Response('rate limited', 429)),
        apiKey: 'pk.k',
      );
      expect(await service.search('anywhere'), isNull);

      final empty = GeocodingService(
        client: MockClient((req) async => _hit(const [])),
        apiKey: 'pk.k',
      );
      expect(await empty.search('nowhere'), isNull);
    });

    test('empty query short-circuits without a request', () async {
      var calls = 0;
      final service = GeocodingService(
        client: MockClient((req) async {
          calls++;
          return _hit(const []);
        }),
        apiKey: 'pk.k',
      );

      expect(await service.search('   '), isNull);
      expect(calls, 0);
    });
  });
}
