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

    test('a failed request is tried again next time', () async {
      var calls = 0;
      final service = GeocodingService(
        client: MockClient((req) async {
          calls++;
          return calls == 1
              ? http.Response('rate limited', 429)
              : _hit([
                  {'lat': '19.0760', 'lon': '72.8777'},
                ]);
        }),
        apiKey: 'pk.k',
      );

      expect(await service.search('Mumbai'), isNull);
      expect(await service.search('Mumbai'), LatLng(19.0760, 72.8777));
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

  group('GeocodingService.locate', () {
    const address =
        'Flat 4, Sai Residency, Temple Road, KPHB Colony, Hyderabad, '
        'Hyderabad, Telangana, 500072';

    test('widens the address, dropping repeated parts', () {
      expect(GeocodingService.addressQueries(address), [
        'Flat 4, Sai Residency, Temple Road, KPHB Colony, Hyderabad, '
            'Telangana, 500072',
        'KPHB Colony, Hyderabad, Telangana, 500072',
        'Hyderabad, Telangana, 500072',
        '500072, India',
      ]);
    });

    test('tries a short address once, plus its PIN code', () {
      expect(GeocodingService.addressQueries('12 Baker Street'), [
        '12 Baker Street',
      ]);
      expect(GeocodingService.addressQueries('KPHB Colony, 500072'), [
        'KPHB Colony, 500072',
        '500072, India',
      ]);
      expect(GeocodingService.addressQueries(' , '), isEmpty);
    });

    /// A service that only knows [match], with the pauses it asked for.
    ({GeocodingService service, List<String> asked, List<Duration> pauses})
    knowing(String match, {int status = 200}) {
      final asked = <String>[];
      final pauses = <Duration>[];
      final service = GeocodingService(
        client: MockClient((req) async {
          final query = req.url.queryParameters['q']!;
          asked.add(query);
          if (status != 200) return http.Response('error', status);
          return query == match
              ? _hit([
                  {'lat': '17.4933', 'lon': '78.3915'},
                ])
              : http.Response('{"error":"Unable to geocode"}', 404);
        }),
        apiKey: 'pk.k',
        pause: (gap) async => pauses.add(gap),
      );
      return (service: service, asked: asked, pauses: pauses);
    }

    test('stops at the first form that is found, spacing requests', () async {
      final (:service, :asked, :pauses) = knowing(
        'KPHB Colony, Hyderabad, Telangana, 500072',
      );

      expect(await service.locate(address), LatLng(17.4933, 78.3915));
      expect(asked, hasLength(2));
      expect(pauses, [const Duration(milliseconds: 600)]);

      // Both answers are remembered: no more requests, no more waiting.
      expect(await service.locate(address), LatLng(17.4933, 78.3915));
      expect(asked, hasLength(2));
      expect(pauses, hasLength(1));
    });

    test('gives up after four forms when nothing is found', () async {
      final (:service, :asked, pauses: _) = knowing('nothing');

      expect(await service.locate(address), isNull);
      expect(asked, hasLength(4));
    });

    test('stops when a request fails', () async {
      final (:service, :asked, pauses: _) = knowing('nothing', status: 503);

      expect(await service.locate(address), isNull);
      expect(asked, hasLength(1));
    });
  });
}
