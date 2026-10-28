import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../data/fleet_providers.dart';
import '../domain/fleet_rules.dart';
import 'fleet_screen.dart';

/// Opens the manage sheet for one van.
Future<void> showVehicleSheet(
  BuildContext context,
  WidgetRef ref,
  String vehicleId,
) => LpgFeedback.showSheet<void>(
  context,
  title: 'Van',
  builder: (_) => _VehicleSheet(vehicleId: vehicleId),
);

class _VehicleSheet extends ConsumerStatefulWidget {
  const _VehicleSheet({required this.vehicleId});

  final String vehicleId;

  @override
  ConsumerState<_VehicleSheet> createState() => _VehicleSheetState();
}

class _VehicleSheetState extends ConsumerState<_VehicleSheet> {
  var _busy = false;
  var _editing = false;
  String? _error;
  final _make = TextEditingController();
  final _model = TextEditingController();
  final _capacity = TextEditingController();
  var _ownership = 'owned';

  @override
  void dispose() {
    _make.dispose();
    _model.dispose();
    _capacity.dispose();
    super.dispose();
  }

  Future<void> _run(
    Future<Result<Object?>> Function() call, {
    String? success,
  }) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await call();
    if (!mounted) return;
    switch (result) {
      case FailureResult<Object?>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
      case Success<Object?>():
        refreshFleet(ref);
        setState(() {
          _busy = false;
          _editing = false;
        });
        if (success != null) {
          LpgFeedback.showToast(context, success, tone: LpgTone.success);
        }
    }
  }

  Future<void> _changeStatus(FleetVehicle vehicle, String status) async {
    if (status == 'inactive') {
      final ok = await LpgFeedback.confirm(
        context,
        title: 'Deactivate ${vehicle.registrationNumber}?',
        message:
            "It can't be put on trips any more. This can't be undone from "
            'the app.',
        confirmLabel: 'Deactivate',
        destructive: true,
      );
      if (!ok) return;
    }
    await _run(
      () => ref.read(fleetApiProvider).setVehicleStatus(vehicle.id, status),
      success:
          '${vehicle.registrationNumber} is now '
          '${fleetStatusLabel(status).toLowerCase()}.',
    );
  }

  Future<void> _save(FleetVehicle vehicle) async {
    final capacity = int.tryParse(_capacity.text.trim());
    if (_make.text.trim().isEmpty || _model.text.trim().isEmpty) {
      setState(() => _error = 'Enter the make and model.');
      return;
    }
    if (capacity == null || capacity < 1) {
      setState(() => _error = 'Capacity must be at least 1.');
      return;
    }
    await _run(
      () => ref
          .read(fleetApiProvider)
          .updateVehicleDetails(
            vehicle.id,
            make: _make.text.trim(),
            model: _model.text.trim(),
            ownershipType: _ownership,
            capacityUnits: capacity,
          ),
      success: 'Van updated.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final vehicle = ref
        .watch(fleetVehiclesProvider)
        .value
        ?.where((v) => v.id == widget.vehicleId)
        .firstOrNull;
    final branches = ref.watch(fleetBranchesProvider).value ?? const [];
    if (vehicle == null) {
      return const Padding(
        padding: EdgeInsets.all(LpgSpacing.xl),
        child: Center(child: LpgLoadingIndicator()),
      );
    }
    final targets = vehicleStatusTargets[vehicle.status] ?? const <String>[];

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const LpgIconBox(icon: LpgIcons.truck),
              const SizedBox(width: LpgSpacing.md),
              Expanded(
                child: Text(
                  vehicle.registrationNumber,
                  style: text.titleMedium,
                ),
              ),
              LpgStatusBadge(
                label: fleetStatusLabel(vehicle.status),
                severity: fleetStatusSeverity(vehicle.status),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          if (_error != null) ...[
            LpgBanner(tone: LpgTone.danger, message: _error!),
            const SizedBox(height: LpgSpacing.md),
          ],
          LpgKeyValueRow(
            label: 'Branch',
            value: branchName(branches, vehicle.branchId),
          ),
          if (!_editing) ...[
            LpgKeyValueRow(
              label: 'Make and model',
              value: '${vehicle.make} ${vehicle.model}'.trim().isEmpty
                  ? '—'
                  : '${vehicle.make} ${vehicle.model}'.trim(),
            ),
            LpgKeyValueRow(
              label: 'Ownership',
              value:
                  ownershipTypes[vehicle.ownershipType] ??
                  LpgFormat.sentence(vehicle.ownershipType),
            ),
            LpgKeyValueRow(
              label: 'Capacity',
              value: '${vehicle.capacityUnits} cylinders',
            ),
          ] else ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgTextField(
              label: 'Make',
              isRequired: true,
              controller: _make,
              textCapitalization: TextCapitalization.words,
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgTextField(
              label: 'Model',
              isRequired: true,
              controller: _model,
              textCapitalization: TextCapitalization.words,
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgDropdownField<String>(
              label: 'Ownership',
              value: _ownership,
              items: ownershipTypes,
              onChanged: (v) => setState(() => _ownership = v ?? 'owned'),
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgTextField(
              label: 'Capacity (cylinders)',
              isRequired: true,
              controller: _capacity,
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgButton(
              label: 'Save',
              expand: true,
              isLoading: _busy,
              onPressed: _busy ? null : () => _save(vehicle),
            ),
            LpgButton(
              label: 'Cancel',
              variant: LpgButtonVariant.text,
              onPressed: _busy ? null : () => setState(() => _editing = false),
            ),
          ],
          const SizedBox(height: LpgSpacing.lg),
          if (!_editing && vehicle.status != 'inactive')
            LpgButton(
              label: 'Edit details',
              icon: LpgIcons.edit,
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: _busy
                  ? null
                  : () => setState(() {
                      _editing = true;
                      _make.text = vehicle.make;
                      _model.text = vehicle.model;
                      _capacity.text = '${vehicle.capacityUnits}';
                      _ownership =
                          ownershipTypes.containsKey(vehicle.ownershipType)
                          ? vehicle.ownershipType
                          : 'owned';
                    }),
            ),
          for (final status in targets) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgButton(
              label: fleetStatusAction(status),
              variant: status == 'inactive'
                  ? LpgButtonVariant.destructive
                  : LpgButtonVariant.tonal,
              expand: true,
              onPressed: _busy ? null : () => _changeStatus(vehicle, status),
            ),
          ],
          if (vehicle.status == 'inactive')
            Text(
              'This van is inactive and cannot be put on trips.',
              style: text.bodySmall?.copyWith(color: colors.textSecondary),
            ),
          const SizedBox(height: LpgSpacing.md),
        ],
      ),
    );
  }
}
