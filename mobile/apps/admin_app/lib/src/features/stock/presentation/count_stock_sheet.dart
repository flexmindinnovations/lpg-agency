import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../orders/data/orders_provider.dart';
import 'stock_presentation.dart';

/// Records what was physically counted for one cylinder type and status.
/// Stock does not change yet: the count waits for someone to approve it.
/// Pops `true` once it is recorded.
class CountStockSheet extends ConsumerStatefulWidget {
  const CountStockSheet({super.key, required this.godown, required this.lines});

  final FleetWarehouse godown;

  /// What the godown holds now, so the sheet can say what the system expects.
  final List<StockBalanceLine> lines;

  @override
  ConsumerState<CountStockSheet> createState() => _CountStockSheetState();
}

class _CountStockSheetState extends ConsumerState<CountStockSheet> {
  final _counted = TextEditingController();
  String? _typeId;
  String _status = 'filled';
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _counted.dispose();
    super.dispose();
  }

  int get _expected => widget.lines
      .where((l) => l.cylinderTypeId == _typeId && l.status == _status)
      .fold(0, (sum, l) => sum + l.quantity);

  Future<void> _submit() async {
    final counted = int.tryParse(_counted.text.trim());
    if (_typeId == null) {
      setState(() => _error = 'Choose which cylinder you counted.');
      return;
    }
    if (counted == null) {
      setState(() => _error = 'Enter how many you counted. Use 0 if none.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(fleetApiProvider)
        .recordCount(
          'warehouse',
          widget.godown.id,
          cylinderTypeId: _typeId!,
          status: _status,
          actualQuantity: counted,
        );
    if (!mounted) return;
    switch (result) {
      case Success<ReconciliationRecord>():
        Navigator.of(context).pop(true);
      case FailureResult<ReconciliationRecord>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final catalog = ref.watch(cylinderCatalogProvider);

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Count the cylinders on the shelves at ${widget.godown.name}.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          catalog.when(
            loading: () => const LpgSkeleton(height: 56),
            error: (_, _) => Text(
              'Could not load the cylinder list.',
              style: text.bodyMedium?.copyWith(color: colors.statusDanger),
            ),
            data: (types) => LpgDropdownField<String>(
              label: 'Cylinder',
              prefixIcon: LpgIcons.cylinder,
              placeholder: 'Choose the cylinder',
              value: _typeId ?? '',
              items: {
                for (final t in types)
                  if (t.isActive) t.id: t.name,
              },
              onChanged: _busy ? null : (v) => setState(() => _typeId = v),
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgDropdownField<String>(
            label: 'Which cylinders',
            value: _status,
            items: stockStatusLabels,
            onChanged: _busy
                ? null
                : (v) {
                    if (v != null) setState(() => _status = v);
                  },
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'How many you counted',
            helperText: _typeId == null ? null : 'The system shows $_expected.',
            controller: _counted,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(5),
            ],
            enabled: !_busy,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Record count',
            icon: LpgIcons.check,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}
