import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../orders/data/orders_provider.dart';

/// Closes out a trip that has come back. The server settles it only once
/// the van has an approved stock count, so this tries to settle, and if it
/// can't, takes the count (what is on the van now), approves it, and
/// settles. A count someone else already recorded is approved instead of
/// being counted twice. Pops `true` once the trip is settled.
class SettleTripSheet extends ConsumerStatefulWidget {
  const SettleTripSheet({super.key, required this.trip});

  final RouteSummary trip;

  @override
  ConsumerState<SettleTripSheet> createState() => _SettleTripSheetState();
}

class _SettleTripSheetState extends ConsumerState<SettleTripSheet> {
  /// `null` while checking whether the trip can be settled as it is.
  var _checking = true;
  var _busy = false;
  String? _error;
  String? _note;

  List<StockBalanceLine> _lines = const [];
  List<ReconciliationRecord> _pending = const [];
  final Map<String, TextEditingController> _counts = {};

  String _key(StockBalanceLine l) => '${l.cylinderTypeId}|${l.status}';

  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void dispose() {
    for (final c in _counts.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _start() async {
    final settled = await ref
        .read(routeApiProvider)
        .settleRoute(widget.trip.id);
    if (!mounted) return;
    if (settled is Success<RouteSummary>) {
      Navigator.of(context).pop(true);
      return;
    }
    final failure = (settled as FailureResult<RouteSummary>).failure;
    if (failure.errorCode != 'ROUTE_RECONCILIATION_PENDING') {
      setState(() {
        _checking = false;
        _error = failure.message;
      });
      return;
    }

    final api = ref.read(fleetApiProvider);
    final vehicleId = widget.trip.vehicleId;
    final results = await (
      api.getBalanceLines('vehicle', vehicleId),
      api.listReconciliations('vehicle', vehicleId),
    ).wait;
    if (!mounted) return;
    final lines = switch (results.$1) {
      Success<List<StockBalanceLine>>(:final value) => value,
      _ => const <StockBalanceLine>[],
    };
    final records = switch (results.$2) {
      Success<List<ReconciliationRecord>>(:final value) => value,
      _ => const <ReconciliationRecord>[],
    };
    for (final l in lines) {
      _counts[_key(l)] = TextEditingController(text: '${l.quantity}');
    }
    setState(() {
      _checking = false;
      _lines = lines;
      _pending = [
        for (final r in records)
          if (r.isPending) r,
      ];
      if (results.$1 is FailureResult) {
        _error = (results.$1 as FailureResult).failure.message;
      }
    });
  }

  Future<void> _approveAllAndSettle(List<ReconciliationRecord> records) async {
    final api = ref.read(fleetApiProvider);
    for (final r in records) {
      final approved = await api.approveCount(r.id);
      if (!mounted) return;
      if (approved case FailureResult<ReconciliationRecord>(:final failure)) {
        setState(() {
          _busy = false;
          _error = failure.errorCode == 'SELF_APPROVAL_NOT_ALLOWED'
              ? 'The count is recorded. Someone other than the person who '
                    'counted has to approve it, then settle the trip again.'
              : failure.message;
        });
        return;
      }
    }
    final settled = await ref
        .read(routeApiProvider)
        .settleRoute(widget.trip.id);
    if (!mounted) return;
    switch (settled) {
      case Success<RouteSummary>():
        ref.invalidate(fleetProvider);
        Navigator.of(context).pop(true);
      case FailureResult<RouteSummary>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  Future<void> _submitCount() async {
    final counts = <StockBalanceLine, int>{};
    for (final l in _lines) {
      final n = int.tryParse(_counts[_key(l)]!.text.trim());
      if (n == null || n < 0) {
        setState(() => _error = 'Enter a count of 0 or more for every line.');
        return;
      }
      counts[l] = n;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(fleetApiProvider);
    final recorded = <ReconciliationRecord>[];
    for (final e in counts.entries) {
      final result = await api.recordCount(
        'vehicle',
        widget.trip.vehicleId,
        cylinderTypeId: e.key.cylinderTypeId,
        status: e.key.status,
        actualQuantity: e.value,
      );
      if (!mounted) return;
      switch (result) {
        case Success<ReconciliationRecord>(:final value):
          recorded.add(value);
        case FailureResult<ReconciliationRecord>(:final failure):
          setState(() {
            _busy = false;
            _error = failure.message;
          });
          return;
      }
    }
    await _approveAllAndSettle(recorded);
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};

    if (_checking) {
      return const Padding(
        padding: EdgeInsets.all(LpgSpacing.xl),
        child: Center(child: LpgLoadingIndicator()),
      );
    }

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (_note != null) ...[
            LpgBanner(tone: LpgTone.info, message: _note!),
            const SizedBox(height: LpgSpacing.md),
          ],
          if (_error != null) ...[
            LpgBanner(tone: LpgTone.danger, message: _error!),
            const SizedBox(height: LpgSpacing.md),
          ],
          if (_pending.isNotEmpty) ...[
            Text(
              'A count of this van is waiting for approval.',
              style: text.bodyMedium,
            ),
            const SizedBox(height: LpgSpacing.sm),
            for (final r in _pending)
              LpgKeyValueRow(
                label:
                    '${names[r.cylinderTypeId] ?? 'Cylinder'} · '
                    '${LpgFormat.statusLabel(r.status)}',
                value:
                    '${r.actualQuantity} counted'
                    '${r.variance == 0 ? '' : ' (${r.variance > 0 ? '+' : ''}${r.variance})'}',
              ),
            const SizedBox(height: LpgSpacing.lg),
            LpgButton(
              label: 'Approve count and settle',
              icon: LpgIcons.check,
              expand: true,
              isLoading: _busy,
              onPressed: _busy
                  ? null
                  : () {
                      setState(() {
                        _busy = true;
                        _error = null;
                      });
                      _approveAllAndSettle(_pending);
                    },
            ),
          ] else if (_lines.isEmpty && _error == null) ...[
            Text(
              'Nothing is recorded on this van, so there is nothing to count.',
              style: text.bodyMedium?.copyWith(color: colors.textSecondary),
            ),
          ] else if (_lines.isNotEmpty) ...[
            Text(
              'Count what is on the van now. Change a number if the count '
              'differs; the difference is booked when the count is approved.',
              style: text.bodyMedium?.copyWith(color: colors.textSecondary),
            ),
            const SizedBox(height: LpgSpacing.md),
            for (final l in _lines) ...[
              LpgTextField(
                label:
                    '${names[l.cylinderTypeId] ?? 'Cylinder'} · '
                    '${LpgFormat.statusLabel(l.status)}',
                helperText: 'Expected ${l.quantity}',
                controller: _counts[_key(l)],
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                enabled: !_busy,
              ),
              const SizedBox(height: LpgSpacing.md),
            ],
            LpgButton(
              label: 'Record count and settle',
              icon: LpgIcons.check,
              expand: true,
              isLoading: _busy,
              onPressed: _busy ? null : _submitCount,
            ),
          ],
          const SizedBox(height: LpgSpacing.md),
        ],
      ),
    );
  }
}
