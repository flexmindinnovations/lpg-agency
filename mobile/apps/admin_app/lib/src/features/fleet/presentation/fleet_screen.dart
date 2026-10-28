import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../orders/data/orders_provider.dart';
import '../data/fleet_providers.dart';
import '../domain/fleet_rules.dart';
import 'driver_detail_sheet.dart';
import 'vehicle_detail_sheet.dart';

/// Drivers and vans: who and what can go out on a trip. Reached from the
/// Dispatch tab and from the empty driver / van pickers on the Send out sheet.
class FleetScreen extends ConsumerWidget {
  const FleetScreen({super.key, this.initialTab = 0});

  /// 0 for drivers, 1 for vans.
  final int initialTab;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 2,
      initialIndex: initialTab.clamp(0, 1),
      child: Builder(
        builder: (context) {
          final tabs = DefaultTabController.of(context);
          return Scaffold(
            appBar: AppBar(
              title: const Text('Drivers and vans'),
              bottom: const TabBar(
                tabs: [
                  Tab(text: 'Drivers'),
                  Tab(text: 'Vans'),
                ],
              ),
            ),
            floatingActionButton: ListenableBuilder(
              listenable: tabs,
              builder: (context, _) => FloatingActionButton.extended(
                onPressed: () => context.pushNamed(
                  tabs.index == 0 ? 'fleet_driver_new' : 'fleet_vehicle_new',
                ),
                icon: const Icon(LpgIcons.add),
                label: Text(tabs.index == 0 ? 'Add driver' : 'Add van'),
              ),
            ),
            body: const TabBarView(children: [_DriversTab(), _VehiclesTab()]),
          );
        },
      ),
    );
  }
}

void refreshFleet(WidgetRef ref) {
  ref.invalidate(fleetDriversProvider);
  ref.invalidate(fleetVehiclesProvider);
  ref.invalidate(driverEmployeesProvider);
  ref.invalidate(fleetProvider);
}

class _DriversTab extends ConsumerWidget {
  const _DriversTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final driversAsync = ref.watch(fleetDriversProvider);
    final branches = ref.watch(fleetBranchesProvider).value ?? const [];

    return RefreshIndicator(
      onRefresh: () async {
        refreshFleet(ref);
        await ref.read(fleetDriversProvider.future);
      },
      child: driversAsync.when(
        loading: () => const Padding(
          padding: LpgSpacing.page,
          child: LpgSkeletonList(itemCount: 4),
        ),
        error: (err, _) => ListView(
          padding: LpgSpacing.page,
          children: [
            LpgErrorState(
              message: errorMessage(err),
              onRetry: () => ref.invalidate(fleetDriversProvider),
            ),
          ],
        ),
        data: (drivers) {
          if (drivers.isEmpty) {
            return ListView(
              padding: LpgSpacing.page,
              children: [
                LpgEmptyState(
                  icon: LpgIcons.user,
                  title: 'No drivers yet',
                  message:
                      'Add a driver so orders can be sent out. You need '
                      'their licence photo and mobile number.',
                  actionLabel: 'Add driver',
                  actionIcon: LpgIcons.add,
                  onAction: () => context.pushNamed('fleet_driver_new'),
                ),
              ],
            );
          }
          return ListView(
            padding: LpgSpacing.page.copyWith(bottom: 96),
            children: [
              for (final d in drivers) ...[
                LpgCard(
                  onTap: () => showDriverSheet(context, ref, d.id),
                  child: Row(
                    children: [
                      LpgAvatar(name: d.name),
                      const SizedBox(width: LpgSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(d.name, style: text.titleSmall),
                            Text(
                              [
                                branchName(branches, d.branchId),
                                if (d.phoneNumber != null) d.phoneNumber!,
                              ].join(' · '),
                              style: text.bodySmall?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                            if (!d.hasLogin)
                              Text(
                                'No Driver App login yet',
                                style: text.bodySmall?.copyWith(
                                  color: colors.statusWarning,
                                ),
                              ),
                          ],
                        ),
                      ),
                      LpgStatusBadge(
                        label: fleetStatusLabel(d.status),
                        severity: fleetStatusSeverity(d.status),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: LpgSpacing.sm),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _VehiclesTab extends ConsumerWidget {
  const _VehiclesTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final vehiclesAsync = ref.watch(fleetVehiclesProvider);
    final branches = ref.watch(fleetBranchesProvider).value ?? const [];

    return RefreshIndicator(
      onRefresh: () async {
        refreshFleet(ref);
        await ref.read(fleetVehiclesProvider.future);
      },
      child: vehiclesAsync.when(
        loading: () => const Padding(
          padding: LpgSpacing.page,
          child: LpgSkeletonList(itemCount: 4),
        ),
        error: (err, _) => ListView(
          padding: LpgSpacing.page,
          children: [
            LpgErrorState(
              message: errorMessage(err),
              onRetry: () => ref.invalidate(fleetVehiclesProvider),
            ),
          ],
        ),
        data: (vehicles) {
          if (vehicles.isEmpty) {
            return ListView(
              padding: LpgSpacing.page,
              children: [
                LpgEmptyState(
                  icon: LpgIcons.truck,
                  title: 'No vans yet',
                  message:
                      'Add a van so orders can be sent out. You need its '
                      'registration certificate photo.',
                  actionLabel: 'Add van',
                  actionIcon: LpgIcons.add,
                  onAction: () => context.pushNamed('fleet_vehicle_new'),
                ),
              ],
            );
          }
          return ListView(
            padding: LpgSpacing.page.copyWith(bottom: 96),
            children: [
              for (final v in vehicles) ...[
                LpgCard(
                  onTap: () => showVehicleSheet(context, ref, v.id),
                  child: Row(
                    children: [
                      const LpgIconBox(icon: LpgIcons.truck),
                      const SizedBox(width: LpgSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(v.registrationNumber, style: text.titleSmall),
                            Text(
                              [
                                if ('${v.make} ${v.model}'.trim().isNotEmpty)
                                  '${v.make} ${v.model}'.trim(),
                                'holds ${v.capacityUnits}',
                                branchName(branches, v.branchId),
                              ].join(' · '),
                              style: text.bodySmall?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      LpgStatusBadge(
                        label: fleetStatusLabel(v.status),
                        severity: fleetStatusSeverity(v.status),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: LpgSpacing.sm),
              ],
            ],
          );
        },
      ),
    );
  }
}
