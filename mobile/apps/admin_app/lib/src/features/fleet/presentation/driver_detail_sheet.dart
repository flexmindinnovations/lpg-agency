import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../data/fleet_providers.dart';
import '../domain/fleet_rules.dart';
import 'fleet_screen.dart';

/// Opens the manage sheet for one driver.
Future<void> showDriverSheet(
  BuildContext context,
  WidgetRef ref,
  String driverId,
) => LpgFeedback.showSheet<void>(
  context,
  title: 'Driver',
  builder: (_) => _DriverSheet(driverId: driverId),
);

class _DriverSheet extends ConsumerStatefulWidget {
  const _DriverSheet({required this.driverId});

  final String driverId;

  @override
  ConsumerState<_DriverSheet> createState() => _DriverSheetState();
}

class _DriverSheetState extends ConsumerState<_DriverSheet> {
  var _busy = false;
  String? _error;
  var _editing = false;
  final _number = TextEditingController();
  DateTime? _expiry;

  @override
  void dispose() {
    _number.dispose();
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

  Future<void> _changeStatus(FleetDriver driver, String status) async {
    if (status == 'inactive') {
      final ok = await LpgFeedback.confirm(
        context,
        title: 'Deactivate ${driver.name}?',
        message:
            "They can't be put on trips any more. This can't be undone "
            'from the app.',
        confirmLabel: 'Deactivate',
        destructive: true,
      );
      if (!ok) return;
    }
    await _run(
      () => ref.read(fleetApiProvider).setDriverStatus(driver.id, status),
      success:
          '${driver.name} is now ${fleetStatusLabel(status).toLowerCase()}.',
    );
  }

  Future<void> _saveLicence(FleetDriver driver) async {
    final number = _number.text.trim();
    if (number.isEmpty) {
      setState(() => _error = 'Enter the licence number.');
      return;
    }
    await _run(
      () => ref
          .read(fleetApiProvider)
          .updateDriverLicense(
            driver.id,
            licenseNumber: number,
            licenseExpiryDate: _expiry,
          ),
      success: 'Licence updated.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final driver = ref
        .watch(fleetDriversProvider)
        .value
        ?.where((d) => d.id == widget.driverId)
        .firstOrNull;
    final branches = ref.watch(fleetBranchesProvider).value ?? const [];
    if (driver == null) {
      return const Padding(
        padding: EdgeInsets.all(LpgSpacing.xl),
        child: Center(child: LpgLoadingIndicator()),
      );
    }
    final state = expiryState(driver.licenseExpiryDate);
    final targets = driverStatusTargets[driver.status] ?? const <String>[];

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              LpgAvatar(name: driver.name),
              const SizedBox(width: LpgSpacing.md),
              Expanded(child: Text(driver.name, style: text.titleMedium)),
              LpgStatusBadge(
                label: fleetStatusLabel(driver.status),
                severity: fleetStatusSeverity(driver.status),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          if (_error != null) ...[
            LpgBanner(tone: LpgTone.danger, message: _error!),
            const SizedBox(height: LpgSpacing.md),
          ],
          if (driver.phoneNumber != null)
            LpgKeyValueRow(label: 'Mobile', value: driver.phoneNumber!),
          LpgKeyValueRow(
            label: 'Branch',
            value: branchName(branches, driver.branchId),
          ),
          if (!_editing) ...[
            LpgKeyValueRow(
              label: 'Licence number',
              value: driver.licenseNumber ?? '—',
            ),
            LpgKeyValueRow(
              label: 'Licence expiry',
              value: driver.licenseExpiryDate == null
                  ? '—'
                  : LpgFormat.date(driver.licenseExpiryDate!),
            ),
            if (state == ExpiryState.expired)
              const Padding(
                padding: EdgeInsets.only(top: LpgSpacing.sm),
                child: LpgBanner(
                  tone: LpgTone.danger,
                  message: 'This licence has expired. Update it.',
                ),
              )
            else if (state == ExpiryState.expiring)
              const Padding(
                padding: EdgeInsets.only(top: LpgSpacing.sm),
                child: LpgBanner(
                  tone: LpgTone.warning,
                  message: 'This licence expires within 30 days.',
                ),
              ),
          ] else ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgTextField(
              label: 'Licence number',
              isRequired: true,
              controller: _number,
              textCapitalization: TextCapitalization.characters,
            ),
            const SizedBox(height: LpgSpacing.md),
            _ExpiryPicker(
              value: _expiry,
              onChanged: (d) => setState(() => _expiry = d),
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgButton(
              label: 'Save licence',
              expand: true,
              isLoading: _busy,
              onPressed: _busy ? null : () => _saveLicence(driver),
            ),
            LpgButton(
              label: 'Cancel',
              variant: LpgButtonVariant.text,
              onPressed: _busy ? null : () => setState(() => _editing = false),
            ),
          ],
          if (!driver.hasLogin) ...[
            const SizedBox(height: LpgSpacing.md),
            LpgBanner(
              tone: LpgTone.warning,
              message:
                  "${driver.name} can't sign in to the Driver App yet. "
                  'Enable the login to let them in with their mobile number.',
              actionLabel: driver.employeeId == null || _busy
                  ? null
                  : 'Enable login',
              onAction: driver.employeeId == null
                  ? null
                  : () => _run(
                      () => ref
                          .read(fleetApiProvider)
                          .enableDriverLogin(driver.employeeId!),
                      success: 'Driver App login enabled.',
                    ),
            ),
          ],
          const SizedBox(height: LpgSpacing.lg),
          if (!_editing && driver.status != 'inactive')
            LpgButton(
              label: 'Update licence',
              icon: LpgIcons.edit,
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: _busy
                  ? null
                  : () => setState(() {
                      _editing = true;
                      _number.text = driver.licenseNumber ?? '';
                      _expiry = driver.licenseExpiryDate;
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
              onPressed: _busy ? null : () => _changeStatus(driver, status),
            ),
          ],
          if (driver.status == 'inactive')
            Text(
              'This driver is inactive and cannot be put on trips.',
              style: text.bodySmall?.copyWith(color: colors.textSecondary),
            ),
          const SizedBox(height: LpgSpacing.md),
        ],
      ),
    );
  }
}

class _ExpiryPicker extends StatelessWidget {
  const _ExpiryPicker({required this.value, required this.onChanged});

  final DateTime? value;
  final ValueChanged<DateTime> onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            value == null ? 'No expiry date' : LpgFormat.date(value!),
            style: context.lpgText.bodyLarge,
          ),
        ),
        LpgButton(
          label: 'Pick expiry',
          variant: LpgButtonVariant.text,
          icon: LpgIcons.calendar,
          onPressed: () async {
            final now = DateTime.now();
            final picked = await showDatePicker(
              context: context,
              initialDate: value ?? now.add(const Duration(days: 365)),
              firstDate: DateTime(2000),
              lastDate: DateTime(2100),
            );
            if (picked != null) onChanged(picked);
          },
        ),
      ],
    );
  }
}
