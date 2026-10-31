import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../fleet/data/fleet_providers.dart';
import '../../orders/data/orders_provider.dart';
import 'pricing_presentation.dart';

/// Sets a price. With a [row] it changes that cylinder, customer type and
/// branch and shows the prices it replaces; without one it adds a new
/// combination. Saving adds a newer price from now, so the old one stays in
/// the history. Pops `true` once saved.
class SetPriceSheet extends ConsumerStatefulWidget {
  const SetPriceSheet({super.key, this.row});

  final PriceRow? row;

  @override
  ConsumerState<SetPriceSheet> createState() => _SetPriceSheetState();
}

class _SetPriceSheetState extends ConsumerState<SetPriceSheet> {
  late final _price = TextEditingController(
    text: widget.row?.current()?.price.toStringAsFixed(2) ?? '',
  );
  String? _cylinderId;
  String _customerType = 'domestic';
  String? _branchId;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _price.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final row = widget.row;
    final cylinderId = row?.cylinderTypeId ?? _cylinderId;
    final price = double.tryParse(_price.text.trim());
    final String? problem;
    if (cylinderId == null) {
      problem = 'Choose the cylinder.';
    } else if (price == null || price <= 0) {
      problem = 'Enter a price above zero.';
    } else if (price > maxPrice) {
      problem = 'That is more than any cylinder costs. Check the amount.';
    } else if (row?.current()?.price ==
        double.parse(price.toStringAsFixed(2))) {
      problem = 'That is already the price.';
    } else {
      problem = null;
    }
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    final old = row?.current()?.price;
    if (old != null && isLargeChange(old, price!)) {
      final go = await LpgFeedback.confirm(
        context,
        title: 'Change the price by ${changeLabel(old, price)}?',
        message:
            'From ${LpgFormat.currency(old)} to ${LpgFormat.currency(price)}. '
            'Check the amount before saving.',
        confirmLabel: 'Save price',
      );
      if (!go || !mounted) return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(priceListApiProvider)
        .setPrice(
          cylinderTypeId: cylinderId!,
          customerType: row?.customerType ?? _customerType,
          price: price!,
          branchId: row == null ? _branchId : row.branchId,
        );
    if (!mounted) return;
    switch (result) {
      case Success<PriceEntry>():
        Navigator.of(context).pop(true);
      case FailureResult<PriceEntry>(:final failure):
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
    final row = widget.row;
    final catalog = ref.watch(cylinderCatalogProvider).value ?? const [];
    final branches = ref.watch(fleetBranchesProvider).value ?? const [];
    final names = {for (final t in catalog) t.id: t.name};
    final branchNames = {for (final b in branches) b.id: b.name};

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (row != null) ...[
            Text(
              '${names[row.cylinderTypeId] ?? 'Cylinder'} · '
              '${customerTypeLabel(row.customerType)}'
              '${row.branchId == null ? '' : ' · ${branchNames[row.branchId] ?? 'Branch'}'}',
              style: text.bodyMedium?.copyWith(color: colors.textSecondary),
            ),
            const SizedBox(height: LpgSpacing.md),
          ] else ...[
            LpgDropdownField<String>(
              label: 'Cylinder',
              prefixIcon: LpgIcons.cylinder,
              placeholder: 'Choose the cylinder',
              value: _cylinderId ?? '',
              items: {
                for (final t in catalog)
                  if (t.isActive) t.id: t.name,
              },
              onChanged: _busy ? null : (v) => setState(() => _cylinderId = v),
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgDropdownField<String>(
              label: 'Customer type',
              prefixIcon: LpgIcons.customers,
              value: _customerType,
              items: customerTypeLabels,
              onChanged: _busy
                  ? null
                  : (v) {
                      if (v != null) setState(() => _customerType = v);
                    },
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgDropdownField<String>(
              label: 'Branch',
              prefixIcon: LpgIcons.agency,
              placeholder: 'All branches',
              value: _branchId ?? '',
              items: {for (final b in branches) b.id: b.name},
              onChanged: _busy ? null : (v) => setState(() => _branchId = v),
            ),
            const SizedBox(height: LpgSpacing.md),
          ],
          LpgTextField(
            label: row == null ? 'Price' : 'New price',
            controller: _price,
            prefixIcon: LpgIcons.rupee,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9.]')),
              LengthLimitingTextInputFormatter(9),
            ],
            helperText: row?.current() == null
                ? 'Applies from now.'
                : 'Now ${LpgFormat.currency(row!.current()!.price)}. The new price applies from now.',
            enabled: !_busy,
          ),
          if (row != null && row.earlier().isNotEmpty) ...[
            const SizedBox(height: LpgSpacing.md),
            Text('Earlier prices', style: text.titleSmall),
            const SizedBox(height: LpgSpacing.sm),
            LpgGroupedList(
              children: [
                for (final e in row.earlier().take(5))
                  LpgListTile(
                    dense: true,
                    title: 'From ${LpgFormat.date(e.effectiveFrom)}',
                    trailing: Text(
                      LpgFormat.currency(e.price),
                      style: text.titleSmall,
                    ),
                  ),
              ],
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Save price',
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
