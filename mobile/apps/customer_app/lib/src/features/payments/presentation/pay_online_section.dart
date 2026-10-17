import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../providers.dart';
import '../data/order_payments_provider.dart';

/// "Pay online" for one order (ADR-052), shared by the order and invoice
/// detail screens.
///
/// Payment happens on Razorpay's hosted page in the browser, so there is no
/// card or UPI form in the app. When the customer returns to the app the
/// pending payment is re-checked with the backend automatically; the
/// "Check payment status" button does the same on demand. Deliberately
/// built only from shared design-system components so the app-wide UI
/// refresh can restyle it without touching this logic.
class PayOnlineSection extends ConsumerStatefulWidget {
  const PayOnlineSection({
    super.key,
    required this.orderId,
    required this.canPay,
    this.onPaid,
  });

  final String orderId;

  /// Whether the parent screen considers anything payable right now.
  final bool canPay;

  /// Called after a payment is confirmed, so the parent can refetch.
  final VoidCallback? onPaid;

  @override
  ConsumerState<PayOnlineSection> createState() => _PayOnlineSectionState();
}

class _PayOnlineSectionState extends ConsumerState<PayOnlineSection>
    with WidgetsBindingObserver {
  bool _busy = false;
  String? _pendingPaymentId;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _pendingPaymentId != null) {
      _checkStatus(quiet: true);
    }
  }

  Future<void> _pay() async {
    setState(() => _busy = true);
    final result = await ref
        .read(paymentApiProvider)
        .createPaymentLink(widget.orderId);
    if (!mounted) return;

    await result.when(
      onSuccess: (payment) async {
        _pendingPaymentId = payment.onlinePaymentId;
        final opened = await launchUrl(
          Uri.parse(payment.paymentUrl),
          mode: LaunchMode.externalApplication,
        );
        if (!opened && mounted) {
          _showMessage('Could not open the payment page.');
        }
      },
      onFailure: (failure) async =>
          _showMessage('Could not start payment: ${failure.message}'),
    );
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _checkStatus({bool quiet = false}) async {
    final paymentId = _pendingPaymentId;
    if (paymentId == null) return;
    setState(() => _busy = true);
    final result = await ref.read(paymentApiProvider).refreshPayment(paymentId);
    if (!mounted) return;
    setState(() => _busy = false);

    result.when(
      onSuccess: (payment) {
        ref.invalidate(orderPaymentsProvider(widget.orderId));
        if (payment.isPaid) {
          _pendingPaymentId = null;
          widget.onPaid?.call();
          _showMessage('Payment received. Thank you!');
        } else if (!quiet) {
          _showMessage(
            payment.isOpen
                ? 'We have not received this payment yet.'
                : 'This payment link has ${payment.status}. Please try again.',
          );
        }
      },
      onFailure: (failure) {
        if (!quiet) _showMessage('Could not check payment: ${failure.message}');
      },
    );
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final payments =
        ref.watch(orderPaymentsProvider(widget.orderId)).asData?.value ??
        const <OnlinePaymentResponse>[];
    final paid = payments.where((p) => p.isPaid).toList();
    final showPayButton = widget.canPay && paid.isEmpty;

    if (paid.isEmpty && !showPayButton) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final payment in paid)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: LpgCard(
              child: Row(
                children: [
                  Icon(Icons.verified_outlined, color: colors.statusSuccess),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Paid online'
                      '${payment.paymentMethod != null ? ' via ${payment.paymentMethod!.toUpperCase()}' : ''}',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colors.textPrimary,
                      ),
                    ),
                  ),
                  Text(
                    '₹${payment.amount.toStringAsFixed(2)}',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: colors.statusSuccess,
                    ),
                  ),
                ],
              ),
            ),
          ),
        if (showPayButton) ...[
          LpgButton(
            label: 'Pay Online',
            icon: Icons.account_balance_wallet_outlined,
            expand: true,
            isLoading: _busy && _pendingPaymentId == null,
            onPressed: _busy ? null : _pay,
          ),
          if (_pendingPaymentId != null) ...[
            const SizedBox(height: 12),
            LpgButton(
              label: 'Check Payment Status',
              variant: LpgButtonVariant.secondary,
              expand: true,
              isLoading: _busy,
              onPressed: _busy ? null : _checkStatus,
            ),
          ],
          const SizedBox(height: 8),
          Text(
            'UPI, cards, net banking and wallets, secured by Razorpay.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.textSecondary,
            ),
          ),
        ],
        const SizedBox(height: 12),
      ],
    );
  }
}
