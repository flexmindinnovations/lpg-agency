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

  /// Why the last attempt to start a payment failed, shown under the
  /// button until the next attempt — a toast alone was gone before most
  /// customers read it (CA-17).
  String? _startError;

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
    setState(() {
      _busy = true;
      _startError = null;
    });
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
          setState(
            () => _startError =
                'Could not open the payment page. Please try again, or pay '
                'the driver on delivery.',
          );
        }
      },
      onFailure: (failure) async {
        if (failure.errorCode == 'SERVICE_UNAVAILABLE') {
          // No gateway after all: stop offering it on this screen.
          ref.invalidate(onlinePaymentAvailableProvider);
        }
        setState(
          () => _startError =
              "Online payment isn't available right now (${failure.message}). "
              'You can pay the driver on delivery.',
        );
      },
    );
    if (mounted) setState(() => _busy = false);
  }

  /// The agency's UPI QR and bank details for this order's balance
  /// (ADR-066): scan it in any UPI app, or pay by bank transfer.
  Future<void> _showUpiQr() async {
    final api = ref.read(paymentApiProvider);
    final qr = await api.getUpiQr(orderId: widget.orderId);
    final profile = await api.getPaymentProfile();
    if (!mounted) return;
    final upi = qr.when(onSuccess: (v) => v, onFailure: (_) => null);
    final bank = profile.when(onSuccess: (v) => v, onFailure: (_) => null);
    if (upi == null && (bank == null || !bank.hasBankDetails)) {
      _showMessage(
        'UPI payment is not set up for this agency yet.',
        tone: LpgTone.warning,
      );
      return;
    }
    await LpgFeedback.showSheet<void>(
      context,
      title: 'Pay by UPI',
      builder: (_) => SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (upi != null)
              LpgUpiQrCard(
                png: upi.png,
                amountText: LpgFormat.currency(upi.amount),
                payeeName: upi.payeeName,
                upiId: upi.upiId,
              ),
            if (bank != null && bank.hasBankDetails) ...[
              const SizedBox(height: LpgSpacing.md),
              LpgCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Or pay by bank transfer',
                      style: context.lpgText.titleSmall,
                    ),
                    const SizedBox(height: LpgSpacing.sm),
                    Text(bank.accountHolder),
                    Text('${bank.bankName} ${bank.branch}'.trim()),
                    Text('A/c ${bank.accountNumber}'),
                    Text('IFSC ${bank.ifsc}'),
                  ],
                ),
              ),
            ],
            const SizedBox(height: LpgSpacing.md),
            Text(
              'Tell the driver once you have paid. The agency confirms the '
              'payment on its side.',
              textAlign: TextAlign.center,
              style: context.lpgText.bodySmall?.copyWith(
                color: context.lpgColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
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
    final available =
        ref.watch(onlinePaymentAvailableProvider).asData?.value ?? false;
    final showPayButton = widget.canPay && available && paid.isEmpty;

    final showUpi = widget.canPay && paid.isEmpty;

    if (paid.isEmpty && !showPayButton && !showUpi) {
      return const SizedBox.shrink();
    }

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
          if (_startError case final error?) ...[
            const SizedBox(height: LpgSpacing.smd),
            LpgBanner(tone: LpgTone.danger, message: error),
          ],
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
        if (showUpi) ...[
          if (showPayButton) const SizedBox(height: LpgSpacing.smd),
          LpgButton(
            label: 'Pay by UPI QR',
            icon: LpgIcons.qrCode,
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: _showUpiQr,
          ),
        ],
        const SizedBox(height: LpgSpacing.md),
      ],
    );
  }
}
