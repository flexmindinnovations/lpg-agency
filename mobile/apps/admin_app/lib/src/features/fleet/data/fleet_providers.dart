import 'package:core/core.dart';
import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

final fleetBranchesProvider = FutureProvider<List<FleetBranch>>((ref) async {
  final result = await ref.watch(fleetApiProvider).listBranches();
  return [
    for (final b in unwrap(result))
      if (b.isActive) b,
  ];
});

final fleetDriversProvider = FutureProvider<List<FleetDriver>>((ref) async {
  return unwrap(await ref.watch(fleetApiProvider).listDrivers());
});

final fleetVehiclesProvider = FutureProvider<List<FleetVehicle>>((ref) async {
  return unwrap(await ref.watch(fleetApiProvider).listVehicles());
});

/// Staff with the driver role, so an existing person can be given a driver
/// profile instead of being registered twice. Roles without `users:read`
/// get an empty list and register a new person.
final driverEmployeesProvider = FutureProvider<List<FleetEmployee>>((
  ref,
) async {
  final result = await ref
      .watch(fleetApiProvider)
      .listEmployees(role: 'driver');
  return switch (result) {
    Success<List<FleetEmployee>>(:final value) => value,
    _ => const <FleetEmployee>[],
  };
});
