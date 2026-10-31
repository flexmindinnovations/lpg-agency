import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';

/// Records a payment received at the office against an invoice. The amount
/// starts at the balance due; a part payment is fine, more than the balance
/// is refused. Cheques and bank transfers need their reference. Pops `true`
/// once the payment is saved.
class RecordPaymentSheet extends ConsumerStatefulWidget {
  const RecordPaymentSheet({super.key, required this.invoice});

  final InvoiceResponse invoice;

  @override
  ConsumerState<RecordPaymentSheet> createState() => _RecordPaymentSheetState();
}

class _RecordPaymentSheetState extends ConsumerState<RecordPaymentSheet> {
  static const _methodIcons = {
    'cash': LpgIcons.cash,
    'upi': LpgIcons.qrCode,
    'cheque': LpgIcons.receipt,
    'bank_transfer': LpgIcons.agency,
  };

  late final _amount = TextEditingController(
    text: widget.invoice.balanceDue.toStringAsFixed(2),
  );
  final _reference = TextEditingController();
  String _chosenMethod = 'cash';

  /// What the agency has set up: UPI needs its UPI ID, bank transfer its bank
  /// details (the payment profile).
  List<PaymentMethodOption> get _offeredMethods =>
      (ref.read(paymentMethodsProvider).value ?? PaymentMethods.cashOnly)
          .office;

  String get _method {
    final offered = _offeredMethods;
    return offered.any((m) => m.code == _chosenMethod)
        ? _chosenMethod
        : offered.first.code;
  }

  String? _error;
  bool _busy = false;

  double get _due => widget.invoice.balanceDue;

  bool get _referenceRequired =>
      _method == 'cheque' || _method == 'bank_transfer';

  String get _referenceLabel => switch (_method) {
    'cheque' => 'Cheque number',
    'bank_transfer' => 'Bank reference (UTR)',
    'upi' => 'UPI transaction id (optional)',
    'card' => 'Card slip number (optional)',
    _ => 'Reference',
  };

  @override
  void dispose() {
    _amount.dispose();
    _reference.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final amount = double.tryParse(_amount.text.trim());
    if (amount == null || amount <= 0) {
      setState(() => _error = 'Enter the amount received.');
      return;
    }
    if (amount > _due + 0.001) {
      setState(
        () => _error =
            'That is more than the ${LpgFormat.currency(_due)} still due.',
      );
      return;
    }
    if (_referenceRequired && _reference.text.trim().isEmpty) {
      setState(() => _error = 'Enter the ${_referenceLabel.toLowerCase()}.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(invoiceApiProvider)
        .recordPayment(
          widget.invoice.invoiceId,
          method: _method,
          amount: amount,
          reference: _reference.text.trim(),
        );
    if (!mounted) return;
    switch (result) {
      case Success<InvoiceResponse>():
        Navigator.of(context).pop(true);
      case FailureResult<InvoiceResponse>(:final failure):
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
    ref.watch(paymentMethodsProvider); // rebuild when it arrives

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${widget.invoice.invoiceNumber ?? 'Invoice'} · '
            '${LpgFormat.currency(_due)} due',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgDropdownField<String>(
            label: 'How was it paid?',
            value: _method,
            items: {for (final m in _offeredMethods) m.code: m.label},
            icons: _methodIcons,
            onChanged: _busy
                ? null
                : (v) {
                    if (v == null) return;
                    setState(() {
                      _chosenMethod = v;
                      _error = null;
                    });
                  },
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Amount received',
            controller: _amount,
            prefixIcon: LpgIcons.rupee,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9.]')),
            ],
            enabled: !_busy,
          ),
          if (_method != 'cash') ...[
            const SizedBox(height: LpgSpacing.md),
            LpgTextField(
              label: _referenceLabel,
              controller: _reference,
              prefixIcon: LpgIcons.number,
              enabled: !_busy,
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Save payment',
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
