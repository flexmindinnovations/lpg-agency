import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../providers.dart';
import '../data/order_payments_provider.dart';

/// "Pay online" for one order (ADR-053), shared by the order and invoice
/// detail screens.
///
/// Payment happens on Razorpay's hosted page in the browser, so there is no
/// card or UPI form in the app. When the customer returns to the app the
/// pending payment is re-checked with the backend automatically; the
/// "Check payment status" button does the same on demand. Built only from
/// design-system components (`LpgCard`, `LpgListTile`, `LpgButton`,
/// `LpgFeedback`) so it follows the app's theme.
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
          _showMessage(
            'Could not open the payment page.',
            tone: LpgTone.danger,
          );
        }
      },
      onFailure: (failure) async => _showMessage(
        'Could not start payment: ${failure.message}',
        tone: LpgTone.danger,
      ),
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
          _showMessage('Payment received. Thank you!', tone: LpgTone.success);
        } else if (!quiet) {
          _showMessage(
            payment.isOpen
                ? 'We have not received this payment yet.'
                : 'This payment link has ${payment.status}. Please try again.',
            tone: LpgTone.warning,
          );
        }
      },
      onFailure: (failure) {
        if (!quiet) {
          _showMessage(
            'Could not check payment: ${failure.message}',
            tone: LpgTone.danger,
          );
        }
      },
    );
  }

  void _showMessage(String message, {LpgTone tone = LpgTone.neutral}) {
    LpgFeedback.showToast(context, message, tone: tone);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
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
            padding: const EdgeInsets.only(bottom: LpgSpacing.smd),
            child: LpgCard(
              padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
              child: LpgListTile(
                leadingIcon: LpgIcons.verified,
                leadingTone: LpgTone.success,
                title: 'Paid online',
                subtitle: payment.paymentMethod != null
                    ? 'via ${payment.paymentMethod!.toUpperCase()}'
                    : null,
                trailing: Text(
                  LpgFormat.currency(payment.amount),
                  style: text.titleSmall?.copyWith(color: colors.statusSuccess),
                ),
              ),
            ),
          ),
        if (showPayButton) ...[
          LpgButton(
            label: 'Pay Online',
            icon: LpgIcons.wallet,
            expand: true,
            isLoading: _busy && _pendingPaymentId == null,
            onPressed: _busy ? null : _pay,
          ),
          if (_pendingPaymentId != null) ...[
            const SizedBox(height: LpgSpacing.smd),
            LpgButton(
              label: 'Check Payment Status',
              icon: LpgIcons.sync,
              variant: LpgButtonVariant.secondary,
              expand: true,
              isLoading: _busy,
              onPressed: _busy ? null : _checkStatus,
            ),
          ],
          const SizedBox(height: LpgSpacing.sm),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                LpgIcons.security,
                size: LpgSizes.iconSm,
                color: colors.textSecondary,
              ),
              const SizedBox(width: LpgSpacing.xs),
              Flexible(
                child: Text(
                  'UPI, cards, net banking and wallets, secured by Razorpay.',
                  textAlign: TextAlign.center,
                  style: text.bodySmall?.copyWith(color: colors.textSecondary),
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: LpgSpacing.md),
      ],
    );
  }
}
