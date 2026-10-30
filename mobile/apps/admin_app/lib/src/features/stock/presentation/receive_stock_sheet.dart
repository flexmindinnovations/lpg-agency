import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../orders/data/orders_provider.dart';
import 'stock_presentation.dart';

/// Books a truck of filled cylinders from the OMC into a godown, with the
/// delivery challan, invoice and truck numbers for the record. Pops the
/// [GoodsReceipt] once it is saved.
class ReceiveStockSheet extends ConsumerStatefulWidget {
  const ReceiveStockSheet({super.key, required this.godown});

  final FleetWarehouse godown;

  @override
  ConsumerState<ReceiveStockSheet> createState() => _ReceiveStockSheetState();
}

class _ReceiveStockSheetState extends ConsumerState<ReceiveStockSheet> {
  final _quantity = TextEditingController();
  final _challan = TextEditingController();
  final _invoice = TextEditingController();
  final _truck = TextEditingController();
  String? _typeId;
  String? _omc;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _quantity.dispose();
    _challan.dispose();
    _invoice.dispose();
    _truck.dispose();
    super.dispose();
  }

  String? _optional(TextEditingController c) {
    final value = c.text.trim();
    return value.isEmpty ? null : value;
  }

  Future<void> _submit() async {
    final quantity = int.tryParse(_quantity.text.trim());
    if (_typeId == null) {
      setState(() => _error = 'Choose which cylinder arrived.');
      return;
    }
    if (quantity == null || quantity < 1) {
      setState(() => _error = 'Enter how many cylinders came off the truck.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(fleetApiProvider)
        .recordGoodsReceipt(
          widget.godown.id,
          cylinderTypeId: _typeId!,
          quantity: quantity,
          sourceOmc: _omc,
          challanNumber: _optional(_challan),
          invoiceNumber: _optional(_invoice),
          truckNumber: _optional(_truck)?.toUpperCase().replaceAll(' ', ''),
        );
    if (!mounted) return;
    switch (result) {
      case Success<GoodsReceipt>(:final value):
        Navigator.of(context).pop(value);
      case FailureResult<GoodsReceipt>(:final failure):
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
            'Filled cylinders arriving at ${widget.godown.name}',
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
          LpgTextField(
            label: 'How many cylinders',
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
            label: 'From (optional)',
            prefixIcon: LpgIcons.truck,
            placeholder: 'Not noted',
            value: _omc ?? '',
            items: omcLabels,
            onChanged: _busy ? null : (v) => setState(() => _omc = v),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Delivery challan number (optional)',
            controller: _challan,
            inputFormatters: [LengthLimitingTextInputFormatter(50)],
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.sm),
          LpgTextField(
            label: 'OMC invoice number (optional)',
            controller: _invoice,
            inputFormatters: [LengthLimitingTextInputFormatter(50)],
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.sm),
          LpgTextField(
            label: 'Truck number (optional)',
            hintText: 'MH12AB1234',
            controller: _truck,
            inputFormatters: [LengthLimitingTextInputFormatter(20)],
            textCapitalization: TextCapitalization.characters,
            enabled: !_busy,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Add to stock',
            icon: LpgIcons.download,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}
