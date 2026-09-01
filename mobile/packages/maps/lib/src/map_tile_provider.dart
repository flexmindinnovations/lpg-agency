import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The tile source for [LocationMap]. `null` means flutter_map's default
/// network provider (LocationIQ/OSM in production). Widget tests override
/// this with an offline fake so the map never hits the network.
final mapTileProviderProvider = Provider<TileProvider?>((ref) => null);
