import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../providers.dart';
import '../../data/orders_provider.dart';
import '../../domain/order_flow.dart';

/// Records the delivery for an order that is out for delivery: the code the
/// customer reads out, what was handed over and collected, and the payment.
/// Pops `true` once the order is delivered.
class DeliverSheet extends ConsumerStatefulWidget {
  const DeliverSheet({super.key, required this.order});

  final OrderResponse order;

  @override
  ConsumerState<DeliverSheet> createState() => _DeliverSheetState();
}

class _DeliverSheetState extends ConsumerState<DeliverSheet> {
  late final TextEditingController _code = TextEditingController();
  final TextEditingController _dac = TextEditingController();
  late final TextEditingController _amount = TextEditingController(
    text: _initialAmount(),
  );
  late final List<int> _delivered = [
    for (final l in widget.order.lines) l.quantityPending,
  ];
  late final List<int> _collected = [for (final _ in widget.order.lines) 0];
  String _method = 'cash';
  String? _error;
  String? _codeError;
  bool _busy = false;
  bool _resending = false;

  String _initialAmount() {
    final total = widget.order.totalAmount ?? 0;
    return total == total.roundToDouble()
        ? total.toStringAsFixed(0)
        : total.toStringAsFixed(2);
  }

  @override
  void dispose() {
    _code.dispose();
    _dac.dispose();
    _amount.dispose();
    super.dispose();
  }

  Future<void> _resend() async {
    setState(() => _resending = true);
    final result = await ref
        .read(orderApiProvider)
        .resendDeliveryOtp(widget.order.id);
    if (!mounted) return;
    setState(() => _resending = false);
    switch (result) {
      case Success<void>():
        LpgFeedback.showToast(
          context,
          'A new code was sent to the customer.',
          tone: LpgTone.success,
        );
      case FailureResult<void>(:final failure):
        LpgFeedback.showToast(context, failure.message, tone: LpgTone.danger);
    }
  }

  Future<void> _send() async {
    final code = _code.text.trim();
    if (code.isEmpty) {
      setState(() => _codeError = "Enter the customer's delivery code.");
      return;
    }
    final dac = _dac.text.trim();
    if (dac.isNotEmpty && !RegExp(r'^\d{6}$').hasMatch(dac)) {
      setState(() => _error = 'The OMC delivery code has 6 digits.');
      return;
    }
    if (_delivered.every((q) => q == 0)) {
      setState(
        () => _error =
            'Hand over at least one cylinder, or record a failed delivery instead.',
      );
      return;
    }
    final amount = double.tryParse(_amount.text.trim());
    if (amount == null || amount < 0) {
      setState(() => _error = 'Enter the amount collected (0 if none).');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _codeError = null;
    });
    final order = widget.order;
    final address = order.deliveryAddress;
    final request = DeliverOrderRequest(
      otpCode: code,
      lines: [
        for (var i = 0; i < order.lines.length; i++)
          DeliveredLineRequest(
            cylinderTypeId: order.lines[i].cylinderTypeId,
            quantityDelivered: _delivered[i],
            quantityCollectedEmpty: _collected[i],
          ),
      ],
      proofOfDelivery: ProofOfDeliverySubmission(
        // Recorded from the office: the order's own delivery point.
        gpsLat: address.latitude ?? 0,
        gpsLng: address.longitude ?? 0,
        paymentMethod: _method,
        amountCollected: amount,
        dacCode: dac.isEmpty ? null : dac,
      ),
    );
    final result = await ref
        .read(orderApiProvider)
        .deliverOrder(order.id, request);
    if (!mounted) return;
    switch (result) {
      case Success<DeliverOrderResponse>():
        Navigator.of(context).pop(true);
      case FailureResult<DeliverOrderResponse>(:final failure):
        setState(() {
          _busy = false;
          if (failure.errorCode?.contains('OTP') ?? false) {
            _codeError = failure.message;
          } else {
            _error = failure.message;
          }
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};
    final lines = widget.order.lines;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgTextField(
            label: 'Delivery code',
            hintText: 'The code the customer received',
            controller: _code,
            isRequired: true,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            errorText: _codeError,
            enabled: !_busy,
            prefixIcon: LpgIcons.lock,
          ),
          Align(
            alignment: Alignment.centerLeft,
            child: LpgButton(
              label: 'Send a new code',
              variant: LpgButtonVariant.text,
              isLoading: _resending,
              onPressed: _busy || _resending ? null : _resend,
            ),
          ),
          const SizedBox(height: LpgSpacing.sm),
          Text('Handed over', style: text.titleSmall),
          for (var i = 0; i < lines.length; i++) ...[
            const SizedBox(height: LpgSpacing.sm),
            Text(
              names[lines[i].cylinderTypeId] ?? 'Cylinder',
              style: text.bodyMedium,
            ),
            const SizedBox(height: LpgSpacing.xs),
            Row(
              children: [
                Expanded(child: Text('Delivered', style: text.bodySmall)),
                LpgQuantityStepper(
                  value: _delivered[i],
                  max: lines[i].quantityPending,
                  semanticLabel: 'Delivered',
                  onChanged: _busy
                      ? null
                      : (v) => setState(() => _delivered[i] = v),
                ),
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: Text('Empties collected', style: text.bodySmall),
                ),
                LpgQuantityStepper(
                  value: _collected[i],
                  semanticLabel: 'Empties collected',
                  onChanged: _busy
                      ? null
                      : (v) => setState(() => _collected[i] = v),
                ),
              ],
            ),
          ],
          const SizedBox(height: LpgSpacing.md),
          Text('Payment', style: text.titleSmall),
          const SizedBox(height: LpgSpacing.sm),
          LpgChoiceChips<String>(
            options: paymentMethods,
            selected: _method,
            onSelected: (value) {
              if (!_busy && value != null) setState(() => _method = value);
            },
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Amount collected',
            controller: _amount,
            isRequired: true,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            prefixText: '₹ ',
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'OMC delivery code (optional)',
            hintText: '6 digits, if the customer has one',
            controller: _dac,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(6),
            ],
            enabled: !_busy,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Record delivery',
            icon: LpgIcons.check,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _send,
          ),
        ],
      ),
    );
  }
}
