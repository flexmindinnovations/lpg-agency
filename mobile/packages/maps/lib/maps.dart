/// Shared map widget + LocationIQ geocoding for the customer and driver apps.
///
/// LocationIQ (keyed with a build-time `LOCATIONIQ_API_KEY` dart-define) backs
/// both the tiles and forward geocoding; without a key it degrades to the raw
/// OpenStreetMap tile CDN + Nominatim (dev/demo only).
library;

export 'package:flutter_map/flutter_map.dart';
export 'package:latlong2/latlong.dart';

export 'src/geocoding_service.dart';
export 'src/location_map.dart';
export 'src/map_tile_provider.dart';
