import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../orders/data/orders_provider.dart';
import '../data/stock_provider.dart';
import 'stock_presentation.dart';

/// How many of [type] are at a godown in [status], from its balance lines.
int onHand(List<StockBalanceLine> lines, String? type, String? status) => lines
    .where((l) => l.cylinderTypeId == type && l.status == status)
    .fold(0, (sum, l) => sum + l.quantity);

/// Cylinder types the godown holds anything of, by name, in catalogue order.
Map<String, String> heldTypes(
  List<StockBalanceLine> lines,
  List<CylinderTypeResponse> catalog,
) {
  final held = {
    for (final l in lines)
      if (l.quantity > 0) l.cylinderTypeId,
  };
  return {
    for (final t in catalog)
      if (held.contains(t.id)) t.id: t.name,
  };
}

/// Moves cylinders from one status to another at a godown: filled to
/// leaking when a valve fails, damaged to scrap, and so on. With
/// [correction] it is a fix to the books instead, which needs a reason and is
/// kept on record. Only moves the server allows are offered. Pops `true`.
class MoveStockSheet extends ConsumerStatefulWidget {
  const MoveStockSheet({
    super.key,
    required this.godown,
    required this.lines,
    this.correction = false,
  });

  final FleetWarehouse godown;
  final List<StockBalanceLine> lines;
  final bool correction;

  @override
  ConsumerState<MoveStockSheet> createState() => _MoveStockSheetState();
}

class _MoveStockSheetState extends ConsumerState<MoveStockSheet> {
  final _quantity = TextEditingController();
  final _reason = TextEditingController();
  String? _typeId;
  String? _from;
  String? _to;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _quantity.dispose();
    _reason.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final qty = int.tryParse(_quantity.text.trim());
    final reason = _reason.text.trim();
    final have = onHand(widget.lines, _typeId, _from);
    final String? problem;
    if (_typeId == null) {
      problem = 'Choose the cylinder.';
    } else if (_from == null) {
      problem = 'Choose where they are now.';
    } else if (_to == null) {
      problem = 'Choose what they become.';
    } else if (qty == null || qty < 1) {
      problem = 'Enter how many.';
    } else if (qty > have) {
      problem =
          'Only $have are recorded as ${stockStatusLabel(_from!).toLowerCase()}.';
    } else if (widget.correction && reason.length < 3) {
      problem = 'Say why, so the correction is on record.';
    } else {
      problem = null;
    }
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(fleetApiProvider);
    final result = widget.correction
        ? await api.adjustStock(
            'warehouse',
            widget.godown.id,
            cylinderTypeId: _typeId!,
            fromStatus: _from!,
            toStatus: _to!,
            quantity: qty!,
            reason: reason,
          )
        : await api.changeStatus(
            'warehouse',
            widget.godown.id,
            cylinderTypeId: _typeId!,
            fromStatus: _from!,
            toStatus: _to!,
            quantity: qty!,
          );
    if (!mounted) return;
    switch (result) {
      case Success<void>():
        Navigator.of(context).pop(true);
      case FailureResult<void>(:final failure):
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
    final catalog = ref.watch(cylinderCatalogProvider).value ?? const [];
    final transitions = ref.watch(statusTransitionsProvider);

    return SingleChildScrollView(
      child: transitions.when(
        loading: () => const Padding(
          padding: EdgeInsets.all(LpgSpacing.lg),
          child: LpgSkeleton(height: 120),
        ),
        error: (_, _) => const LpgBanner(
          tone: LpgTone.danger,
          message: 'Could not load the stock rules. Try again.',
        ),
        data: (rules) {
          final map = widget.correction ? rules.adjustment : rules.statusChange;
          final fromOptions = {
            for (final s in stockStatusLabels.keys)
              if ((map[s] ?? const []).isNotEmpty) s: stockStatusLabels[s]!,
          };
          final toOptions = {
            for (final s in map[_from] ?? const <String>[])
              s: stockStatusLabel(s),
          };
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                widget.correction
                    ? 'Fix the books at ${widget.godown.name}. Use it for a mistake, not for stock that really moved.'
                    : 'Cylinders at ${widget.godown.name} that changed condition.',
                style: text.bodyMedium?.copyWith(color: colors.textSecondary),
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgDropdownField<String>(
                label: 'Cylinder',
                prefixIcon: LpgIcons.cylinder,
                placeholder: 'Choose the cylinder',
                value: _typeId ?? '',
                items: heldTypes(widget.lines, catalog),
                onChanged: _busy ? null : (v) => setState(() => _typeId = v),
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgDropdownField<String>(
                label: 'Now',
                placeholder: 'Choose the status',
                value: _from ?? '',
                items: fromOptions,
                onChanged: _busy
                    ? null
                    : (v) => setState(() {
                        _from = v;
                        _to = null;
                      }),
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgDropdownField<String>(
                label: 'Becomes',
                placeholder: _from == null
                    ? 'Choose "Now" first'
                    : 'Choose the status',
                value: _to ?? '',
                items: toOptions,
                onChanged: _busy || _from == null
                    ? null
                    : (v) => setState(() => _to = v),
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                label: 'How many',
                helperText: _typeId == null || _from == null
                    ? null
                    : 'The system shows ${onHand(widget.lines, _typeId, _from)} ${stockStatusLabel(_from!).toLowerCase()}.',
                controller: _quantity,
                keyboardType: TextInputType.number,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(5),
                ],
                enabled: !_busy,
              ),
              if (widget.correction) ...[
                const SizedBox(height: LpgSpacing.md),
                LpgTextField(
                  label: 'Why',
                  hintText: 'Miscounted at the last receipt…',
                  controller: _reason,
                  maxLines: 2,
                  maxLength: 1000,
                  enabled: !_busy,
                  textCapitalization: TextCapitalization.sentences,
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: LpgSpacing.sm),
                LpgBanner(tone: LpgTone.danger, message: _error!),
              ],
              const SizedBox(height: LpgSpacing.lg),
              LpgButton(
                label: widget.correction ? 'Save correction' : 'Move stock',
                icon: LpgIcons.check,
                isLoading: _busy,
                expand: true,
                onPressed: _busy ? null : _submit,
              ),
            ],
          );
        },
      ),
    );
  }
}

/// Sends empties or defective cylinders back to the oil company's plant,
/// with the challan and truck for the record. Pops the [OmcReturn].
class ReturnToOmcSheet extends ConsumerStatefulWidget {
  const ReturnToOmcSheet({
    super.key,
    required this.godown,
    required this.lines,
  });

  final FleetWarehouse godown;
  final List<StockBalanceLine> lines;

  @override
  ConsumerState<ReturnToOmcSheet> createState() => _ReturnToOmcSheetState();
}

class _ReturnToOmcSheetState extends ConsumerState<ReturnToOmcSheet> {
  /// What the plant takes back.
  static const _returnable = {
    'empty': 'Empty',
    'damaged': 'Damaged',
    'leakage': 'Leaking',
    'quarantine': 'On hold',
  };

  final _quantity = TextEditingController();
  final _challan = TextEditingController();
  final _truck = TextEditingController();
  String? _typeId;
  String _status = 'empty';
  String? _omc;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _quantity.dispose();
    _challan.dispose();
    _truck.dispose();
    super.dispose();
  }

  String? _optional(TextEditingController c) {
    final v = c.text.trim();
    return v.isEmpty ? null : v;
  }

  Future<void> _submit() async {
    final qty = int.tryParse(_quantity.text.trim());
    final have = onHand(widget.lines, _typeId, _status);
    final String? problem;
    if (_typeId == null) {
      problem = 'Choose the cylinder.';
    } else if (_omc == null) {
      problem = 'Choose which oil company they go to.';
    } else if (qty == null || qty < 1) {
      problem = 'Enter how many are going back.';
    } else if (qty > have) {
      problem =
          'Only $have are recorded as ${_returnable[_status]!.toLowerCase()}.';
    } else {
      problem = null;
    }
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(fleetApiProvider)
        .returnToOmc(
          widget.godown.id,
          cylinderTypeId: _typeId!,
          quantity: qty!,
          destinationOmc: _omc!,
          status: _status,
          challanNumber: _optional(_challan),
          truckNumber: _optional(_truck)?.toUpperCase().replaceAll(' ', ''),
        );
    if (!mounted) return;
    switch (result) {
      case Success<OmcReturn>(:final value):
        Navigator.of(context).pop(value);
      case FailureResult<OmcReturn>(:final failure):
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
    final catalog = ref.watch(cylinderCatalogProvider).value ?? const [];

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Cylinders leaving ${widget.godown.name} for the oil company\'s plant.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgDropdownField<String>(
            label: 'Cylinder',
            prefixIcon: LpgIcons.cylinder,
            placeholder: 'Choose the cylinder',
            value: _typeId ?? '',
            items: heldTypes(widget.lines, catalog),
            onChanged: _busy ? null : (v) => setState(() => _typeId = v),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgDropdownField<String>(
            label: 'What is going back',
            value: _status,
            items: _returnable,
            onChanged: _busy
                ? null
                : (v) {
                    if (v != null) setState(() => _status = v);
                  },
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'How many',
            helperText: _typeId == null
                ? null
                : 'The system shows ${onHand(widget.lines, _typeId, _status)} ${_returnable[_status]!.toLowerCase()}.',
            controller: _quantity,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(5),
            ],
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgDropdownField<String>(
            label: 'Going to',
            prefixIcon: LpgIcons.truck,
            placeholder: 'Choose the oil company',
            value: _omc ?? '',
            items: omcLabels,
            onChanged: _busy ? null : (v) => setState(() => _omc = v),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Challan number (optional)',
            controller: _challan,
            inputFormatters: [LengthLimitingTextInputFormatter(50)],
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Truck number (optional)',
            hintText: 'MH12AB1234',
            controller: _truck,
            textCapitalization: TextCapitalization.characters,
            inputFormatters: [LengthLimitingTextInputFormatter(20)],
            enabled: !_busy,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Send back',
            icon: LpgIcons.upload,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}

/// Logs the sample weighed from a truck that has just been received (a tenth
/// of the batch, as the rules suggest). It is optional and never blocks the
/// receipt: Skip leaves it. Pops `true` once saved.
class ReceiptSampleSheet extends ConsumerStatefulWidget {
  const ReceiptSampleSheet({
    super.key,
    required this.godown,
    required this.receipt,
  });

  final FleetWarehouse godown;
  final GoodsReceipt receipt;

  @override
  ConsumerState<ReceiptSampleSheet> createState() => _ReceiptSampleSheetState();
}

class _ReceiptSampleSheetState extends ConsumerState<ReceiptSampleSheet> {
  late final _checked = TextEditingController(
    text: '${suggestedSample(widget.receipt.quantity)}',
  );
  final _underweight = TextEditingController(text: '0');
  String? _scaleId;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _checked.dispose();
    _underweight.dispose();
    super.dispose();
  }

  Future<void> _submit(String scaleId) async {
    final checked = int.tryParse(_checked.text.trim());
    final under = int.tryParse(_underweight.text.trim());
    final batch = widget.receipt.quantity;
    final String? problem;
    if (checked == null || checked < 1 || checked > batch) {
      problem = 'Enter how many were weighed, up to $batch.';
    } else if (under == null || under < 0 || under > checked) {
      problem = 'Enter how many were underweight (0 if none).';
    } else {
      problem = null;
    }
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(weighmentApiProvider)
        .recordReceiptSample(
          widget.receipt.id,
          scaleId: scaleId,
          cylinderTypeId: widget.receipt.cylinderTypeId,
          batch: batch,
          checked: checked!,
          underweight: under!,
        );
    if (!mounted) return;
    switch (result) {
      case Success<WeighmentRecord>():
        Navigator.of(context).pop(true);
      case FailureResult<WeighmentRecord>(:final failure):
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
    final scales = ref.watch(receiptScalesProvider(widget.godown.id));

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${widget.receipt.quantity} cylinders received. Weigh a sample and note it here. '
            'This is optional and does not hold up the receipt.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          scales.when(
            loading: () => const LpgSkeleton(height: 56),
            error: (_, _) => const LpgBanner(
              tone: LpgTone.warning,
              message: 'Could not load the scales. You can skip this.',
            ),
            data: (list) {
              if (list.isEmpty) {
                return const LpgBanner(
                  tone: LpgTone.warning,
                  message:
                      'No certified scale is registered at this godown. Register one on the dashboard to log samples.',
                );
              }
              final id = _scaleId ?? list.first.id;
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  LpgDropdownField<String>(
                    label: 'Scale used',
                    value: id,
                    items: {for (final s in list) s.id: s.assetTag},
                    onChanged: _busy
                        ? null
                        : (v) => setState(() => _scaleId = v),
                  ),
                  const SizedBox(height: LpgSpacing.md),
                  LpgTextField(
                    label: 'Cylinders weighed',
                    helperText: 'A tenth of the batch is suggested.',
                    controller: _checked,
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    enabled: !_busy,
                  ),
                  const SizedBox(height: LpgSpacing.md),
                  LpgTextField(
                    label: 'Underweight cylinders found',
                    helperText:
                        'Set them aside and send them back on the same truck.',
                    controller: _underweight,
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    enabled: !_busy,
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: LpgSpacing.sm),
                    LpgBanner(tone: LpgTone.danger, message: _error!),
                  ],
                  const SizedBox(height: LpgSpacing.lg),
                  LpgButton(
                    label: 'Save sample',
                    icon: LpgIcons.check,
                    isLoading: _busy,
                    expand: true,
                    onPressed: _busy ? null : () => _submit(id),
                  ),
                  const SizedBox(height: LpgSpacing.sm),
                ],
              );
            },
          ),
          LpgButton(
            label: 'Skip',
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: _busy ? null : () => Navigator.of(context).pop(false),
          ),
        ],
      ),
    );
  }
}

/// A tenth of the batch, rounded up, and at least one.
int suggestedSample(int batch) {
  final tenth = (batch / 10).ceil();
  return tenth < 1 ? 1 : tenth;
}
