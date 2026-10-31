import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';

import '../../cash_handover/data/cash_handover_provider.dart';
import '../../../api_provider.dart';
import '../../../dev_otp_provider.dart';
import '../../../offline/delivery_mutations.dart';
import '../../../offline/pending_sync.dart';
import '../data/active_route_provider.dart';
import '../data/image_picker_provider.dart';
import '../data/location_sharing.dart';
import '../data/stop_order_provider.dart';

/// The icon for each payment method code the agency may offer.
const _paymentMethodIcons = {
  'cash': LpgIcons.cash,
  'upi': LpgIcons.wallet,
  'online_gateway': LpgIcons.security,
  'credit': LpgIcons.invoice,
};

/// The proof-of-delivery capture: quantities, payment, the customer's
/// delivery OTP and a GPS stamp, plus an optional signature and photo —
/// then `POST /orders/{id}/deliver`. "Send a new code" re-sends the delivery
/// OTP when the customer lost it or it expired.
class RecordDeliveryScreen extends ConsumerStatefulWidget {
  const RecordDeliveryScreen({super.key, required this.orderId});

  final String orderId;

  @override
  ConsumerState<RecordDeliveryScreen> createState() =>
      _RecordDeliveryScreenState();
}

class _RecordDeliveryScreenState extends ConsumerState<RecordDeliveryScreen> {
  final _signature = SignatureController(penStrokeWidth: 2);
  final _otpController = TextEditingController();
  final _dacController = TextEditingController();
  final _amountController = TextEditingController();

  // cylinderTypeId -> (delivered, collectedEmpty)
  final _quantities = <String, (int, int)>{};
  String _paymentMethod = 'cash';

  /// Only what the agency has set up: a UPI ID for UPI, a connected gateway
  /// for online, a credit limit for on credit.
  List<PaymentMethodOption> get _offeredMethods =>
      (ref.read(paymentMethodsProvider).value ?? PaymentMethods.cashOnly)
          .delivery;

  /// The chosen method, or the first one offered if the agency no longer
  /// offers it.
  String get _method {
    final offered = _offeredMethods;
    return offered.any((m) => m.code == _paymentMethod)
        ? _paymentMethod
        : offered.first.code;
  }

  Uint8List? _photoBytes;
  bool _submitting = false;
  bool _resending = false;
  String? _error;
  bool _prefilled = false;

  /// The error banner beside "Confirm delivery", scrolled into view on error.
  final _errorKey = GlobalKey();

  /// Testing only: the delivery code read back from the dev inbox.
  String? _devCode;

  @override
  void initState() {
    super.initState();
    _loadDevCode();
  }

  Future<void> _loadDevCode() async {
    final code = await ref.read(devDeliveryOtpLookupProvider)(widget.orderId);
    if (mounted && code != null) setState(() => _devCode = code);
  }

  Future<void> _resendCode() async {
    setState(() {
      _resending = true;
      _error = null;
    });
    final result = await ref
        .read(orderApiProvider)
        .resendDeliveryOtp(widget.orderId);
    if (!mounted) return;
    setState(() => _resending = false);
    switch (result) {
      case FailureResult(:final failure):
        _showError(failure.message);
      case Success():
        _otpController.clear();
        LpgFeedback.showToast(
          context,
          'A new code was sent to the customer.',
          tone: LpgTone.success,
        );
        _loadDevCode();
    }
  }

  @override
  void dispose() {
    _signature.dispose();
    _otpController.dispose();
    _dacController.dispose();
    _amountController.dispose();
    super.dispose();
  }

  void _prefill(OrderResponse order) {
    if (_prefilled) return;
    _prefilled = true;
    for (final line in order.lines) {
      final ordered = line.quantityOrdered;
      _quantities[line.cylinderTypeId] = (ordered, ordered);
    }
    // What the customer pays: the price plus GST.
    if (order.amountToPay != null) {
      _amountController.text = order.amountToPay!.toStringAsFixed(2);
    }
  }

  /// Puts [message] in the banner beside "Confirm delivery", scrolls it into
  /// view and buzzes — the driver is often looking at the customer, not the
  /// top of a long form.
  void _showError(String message) {
    if (!mounted) return;
    setState(() => _error = message);
    HapticFeedback.heavyImpact();
    LpgFeedback.showToast(context, message, tone: LpgTone.danger);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final target = _errorKey.currentContext;
      if (target != null && target.mounted) {
        Scrollable.ensureVisible(
          target,
          alignment: 0.5,
          duration: LpgMotion.resolve(
            context,
            normal: LpgTokens.motionDurationMedium,
            reduced: LpgTokens.motionReducedMotionDurationMedium,
          ),
        );
      }
    });
  }

  Future<void> _pickPhoto() async {
    final file = await ref
        .read(imagePickerProvider)
        .pickImage(source: ImageSource.camera, imageQuality: 60);
    if (file == null) return;
    final bytes = await file.readAsBytes();
    if (mounted) setState(() => _photoBytes = bytes);
  }

  Future<void> _submit(OrderResponse order) async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      // Signature and photo are optional; an untouched pad sends none.
      final signatureBytes = _signature.isNotEmpty
          ? await _signature.toPngBytes()
          : null;
      if (_otpController.text.trim().isEmpty) {
        throw Exception('Enter the delivery code the customer received.');
      }
      final amount = double.tryParse(_amountController.text.trim());
      if (amount == null || amount < 0) {
        throw Exception('Enter a valid amount collected.');
      }

      final position = await ref.read(driverGeolocatorProvider).deliveryFix();

      final outcome = await ref
          .read(deliveryMutationsProvider)
          .recordDelivery(
            orderId: order.id,
            lines: [
              for (final line in order.lines)
                DeliveredLineRequest(
                  cylinderTypeId: line.cylinderTypeId,
                  quantityDelivered: _quantities[line.cylinderTypeId]!.$1,
                  quantityCollectedEmpty: _quantities[line.cylinderTypeId]!.$2,
                ),
            ],
            otpCode: _otpController.text.trim(),
            gpsLat: position.latitude,
            gpsLng: position.longitude,
            paymentMethod: _method,
            amountCollected: amount,
            signatureBytes: signatureBytes,
            photoBytes: _photoBytes,
            dacCode: _dacController.text.trim().isEmpty
                ? null
                : _dacController.text.trim(),
          );
      if (!mounted) return;

      switch (outcome) {
        case DeliverFailed(:final message):
          _showError(message);
        case DeliverSynced() || DeliverQueued():
          ref.invalidate(activeRouteProvider);
          ref.invalidate(routeHistoryProvider);
          // The cash to declare and the cash in hand come from the route the
          // delivery may just have completed.
          ref.invalidate(pendingCashHandoversProvider);
          ref.invalidate(myCashInHandProvider);
          LpgFeedback.showToast(
            context,
            outcome is DeliverQueued
                ? 'Delivery saved — it will sync when you are back online.'
                : 'Delivery recorded.',
            tone: LpgTone.success,
          );
          // Back to the route view rather than the stop detail: a delivered
          // order drops out of the driver's visibility (and their last stop
          // completes the route), so popping to `StopDetailScreen` would
          // strand them on a "stop not found" error.
          context.go('/');
      }
    } catch (e) {
      _showError(e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final orderAsync = ref.watch(stopOrderProvider(widget.orderId));

    return Scaffold(
      appBar: AppBar(title: const Text('Record delivery')),
      body: orderAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 4),
        error: (err, _) => LpgErrorState(
          message: 'Could not load this stop.\n$err',
          onRetry: () => ref.invalidate(stopOrderProvider(widget.orderId)),
        ),
        data: (order) {
          _prefill(order);
          // The van's load manifest is a whole-route budget for empties: you
          // can't hand back more empties of a type than the office loaded.
          // Soft — a warning, never a block (a broken check must not strand a
          // driver). `null` for a type means "no manifest", so don't warn.
          final manifest = <String, int>{
            for (final l
                in ref.watch(activeRouteProvider).value?.loadedLines ??
                    const [])
              l.cylinderTypeId: l.quantity,
          };
          final queuedEmpties =
              ref.watch(queuedEmptiesByTypeProvider).value ?? const {};
          ref.watch(paymentMethodsProvider); // rebuild when it arrives
          final offered = _offeredMethods;
          final method = _method;
          return ListView(
            padding: LpgSpacing.page,
            children: [
              const _Section(icon: LpgIcons.cylinder, title: 'Cylinders'),
              for (final line in order.lines)
                Padding(
                  padding: const EdgeInsets.only(bottom: LpgSpacing.sm),
                  child: _QuantityRow(
                    ordered: line.quantityOrdered,
                    delivered: _quantities[line.cylinderTypeId]?.$1 ?? 0,
                    collected: _quantities[line.cylinderTypeId]?.$2 ?? 0,
                    loadedForType: manifest[line.cylinderTypeId],
                    emptiesQueuedElsewhere:
                        queuedEmpties[line.cylinderTypeId] ?? 0,
                    onChanged: (d, c) => setState(
                      () => _quantities[line.cylinderTypeId] = (d, c),
                    ),
                  ),
                ),
              const _Section(icon: LpgIcons.payment, title: 'Payment'),
              LpgDropdownField<String>(
                value: method,
                items: {for (final m in offered) m.code: m.label},
                icons: _paymentMethodIcons,
                onChanged: (v) {
                  if (v != null) setState(() => _paymentMethod = v);
                },
              ),
              if (method == 'upi') ...[
                const SizedBox(height: LpgSpacing.md),
                _UpiQrPanel(orderId: widget.orderId),
              ],
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                label: 'Amount collected',
                prefixIcon: LpgIcons.rupee,
                controller: _amountController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
              ),
              const _Section(icon: LpgIcons.lock, title: 'Delivery code'),
              LpgTextField(
                label: "Customer's code",
                hintText: 'Code from the customer',
                prefixIcon: LpgIcons.number,
                controller: _otpController,
                keyboardType: TextInputType.number,
                autofillHints: const [AutofillHints.oneTimeCode],
              ),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: _resending ? null : _resendCode,
                  icon: const Icon(LpgIcons.sync, size: LpgSizes.iconSm),
                  label: Text(_resending ? 'Sending…' : 'Send a new code'),
                ),
              ),
              if (_devCode case final code?) ...[
                LpgDevOtpBanner(
                  code: code,
                  label: "Testing only: the customer's code is",
                ),
                const SizedBox(height: LpgSpacing.sm),
              ],
              const SizedBox(height: LpgSpacing.smd),
              // Delivery Authentication Code (Phase 20 subsystem 4) — the
              // OMC's own separate code, distinct from the code above.
              // Optional: coverage is ~90%, not 100%, and it never gates
              // delivery.
              LpgTextField(
                label: 'OMC delivery code (DAC)',
                hintText: 'Optional',
                prefixIcon: LpgIcons.verified,
                controller: _dacController,
                keyboardType: TextInputType.number,
              ),
              const _Section(
                icon: LpgIcons.signature,
                title: "Customer's signature (optional)",
              ),
              LpgCard(
                variant: LpgCardVariant.outlined,
                padding: EdgeInsets.zero,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // The pad owns vertical drags so a stroke draws rather
                    // than scrolling; it is kept short so the form still
                    // scrolls above and below it.
                    ClipRRect(
                      borderRadius: const BorderRadius.vertical(
                        top: Radius.circular(LpgRadius.xl),
                      ),
                      child: Signature(
                        controller: _signature,
                        height: _padHeight,
                        backgroundColor: colors.card,
                      ),
                    ),
                    const Divider(height: 1),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        onPressed: _signature.clear,
                        icon: const Icon(
                          LpgIcons.delete,
                          size: LpgSizes.iconSm,
                        ),
                        label: const Text('Clear'),
                      ),
                    ),
                  ],
                ),
              ),
              const _Section(
                icon: LpgIcons.camera,
                title: 'Delivery photo (optional)',
              ),
              if (_photoBytes case final photo?) ...[
                ClipRRect(
                  borderRadius: BorderRadius.circular(LpgRadius.xl),
                  child: Image.memory(
                    photo,
                    height: _padHeight,
                    width: double.infinity,
                    fit: BoxFit.cover,
                  ),
                ),
                const SizedBox(height: LpgSpacing.sm),
              ],
              LpgButton(
                label: _photoBytes == null ? 'Take a photo' : 'Retake',
                icon: _photoBytes == null ? LpgIcons.addPhoto : LpgIcons.camera,
                variant: LpgButtonVariant.secondary,
                expand: true,
                onPressed: _pickPhoto,
              ),
              const SizedBox(height: LpgSpacing.xl),
              if (_error case final error?) ...[
                LpgBanner(
                  key: _errorKey,
                  tone: LpgTone.danger,
                  title: "Delivery wasn't recorded",
                  message: error,
                ),
                const SizedBox(height: LpgSpacing.smd),
              ],
              LpgButton(
                label: 'Confirm delivery',
                icon: LpgIcons.check,
                expand: true,
                isLoading: _submitting,
                onPressed: _submitting ? null : () => _submit(order),
              ),
            ],
          );
        },
      ),
    );
  }

  /// Height of the signature pad and the photo preview.
  static const _padHeight = 160.0;
}

/// A form section heading with its icon.
class _Section extends StatelessWidget {
  const _Section({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Padding(
      padding: const EdgeInsets.only(top: LpgSpacing.lg, bottom: LpgSpacing.sm),
      child: Semantics(
        header: true,
        child: Row(
          children: [
            Icon(icon, size: LpgSizes.iconSm, color: colors.textSecondary),
            const SizedBox(width: LpgSpacing.sm),
            Text(title, style: context.lpgText.titleSmall),
          ],
        ),
      ),
    );
  }
}

class _QuantityRow extends StatelessWidget {
  const _QuantityRow({
    required this.ordered,
    required this.delivered,
    required this.collected,
    required this.onChanged,
    this.loadedForType,
    this.emptiesQueuedElsewhere = 0,
  });

  final int ordered;
  final int delivered;
  final int collected;

  /// How many of this cylinder type the office loaded onto the van, or `null`
  /// when there's no manifest to check against.
  final int? loadedForType;

  /// Empties of this type already recorded (and queued) at other stops on the
  /// route — added to this stop's figure before checking the manifest.
  final int emptiesQueuedElsewhere;

  final void Function(int delivered, int collected) onChanged;

  @override
  Widget build(BuildContext context) {
    final loaded = loadedForType;
    final overLoaded =
        loaded != null && emptiesQueuedElsewhere + collected > loaded;
    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Ordered: $ordered', style: context.lpgText.bodySmall),
          const SizedBox(height: LpgSpacing.sm),
          _Stepper(
            label: 'Delivered',
            value: delivered,
            max: ordered,
            onChanged: (v) => onChanged(v, collected.clamp(0, v)),
          ),
          const SizedBox(height: LpgSpacing.sm),
          _Stepper(
            label: 'Empties collected',
            value: collected,
            max: delivered,
            onChanged: (v) => onChanged(delivered, v),
          ),
          if (overLoaded) ...[
            const SizedBox(height: LpgSpacing.smd),
            LpgBanner(
              tone: LpgTone.warning,
              message:
                  'That is more empties than the van was loaded with for '
                  'this type ($loaded loaded). Recheck before you submit.',
            ),
          ],
        ],
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({
    required this.label,
    required this.value,
    required this.max,
    required this.onChanged,
  });

  final String label;
  final int value;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(label, style: context.lpgText.bodyLarge)),
        LpgQuantityStepper(
          value: value,
          max: max,
          semanticLabel: label,
          onChanged: onChanged,
        ),
      ],
    );
  }
}

/// The agency's UPI QR for this order's balance, for the customer to scan
/// (ADR-066). Needs a connection; offline the driver is told to take the
/// payment another way or ask the customer to pay the UPI ID.
class _UpiQrPanel extends ConsumerWidget {
  const _UpiQrPanel({required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final qr = ref.watch(_upiQrProvider(orderId));
    return qr.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(LpgSpacing.lg),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (_, _) => const _UpiUnavailable(),
      data: (value) => value == null
          ? const _UpiUnavailable()
          : LpgUpiQrCard(
              png: value.png,
              amountText: LpgFormat.currency(value.amount),
              payeeName: value.payeeName,
              upiId: value.upiId,
            ),
    );
  }
}

class _UpiUnavailable extends StatelessWidget {
  const _UpiUnavailable();

  @override
  Widget build(BuildContext context) => const LpgBanner(
    message:
        'The UPI QR is not available right now. Check your connection, or '
        'ask your office to set up the agency UPI ID.',
    tone: LpgTone.warning,
  );
}

final _upiQrProvider = FutureProvider.autoDispose.family<UpiQr?, String>((
  ref,
  orderId,
) async {
  final result = await ref.watch(paymentApiProvider).getUpiQr(orderId: orderId);
  return switch (result) {
    Success(:final value) => value,
    _ => null,
  };
});
