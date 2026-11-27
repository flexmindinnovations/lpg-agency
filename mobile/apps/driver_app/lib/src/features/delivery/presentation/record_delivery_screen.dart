import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';
import 'package:uuid/uuid.dart';

import '../../cash_handover/data/cash_handover_provider.dart';
import '../../../api_provider.dart';
import '../../../dev_otp_provider.dart';
import '../../../offline/delivery_mutations.dart';
import '../../van_load/data/van_load_provider.dart';
import '../data/active_route_provider.dart';
import '../data/held_empties_provider.dart';
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

/// One stop, three steps on one screen (ADR-069): 1 Cylinders (delivered and
/// empties collected), 2 Payment (what is due, what was already paid online,
/// how it is settled), 3 Confirm (the customer's delivery code, GPS stamp,
/// optional signature and photo) — then one `POST /orders/{id}/deliver`. The
/// order is only completed once the payment is settled: the button stays off
/// until the balance is collected or recorded as credit. "Send a new code"
/// re-sends the delivery OTP when the customer lost it or it expired.
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

  // cylinderTypeId -> cylinders delivered
  final _delivered = <String, int>{};

  /// cylinderTypeId -> empties the driver entered. A size the driver has not
  /// touched follows [_emptiesFor].
  final _empties = <String, int>{};
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

  /// The delivery went through; the screen is on its way out and must not
  /// submit again.
  bool _done = false;

  /// One key for every attempt of this delivery, so a second tap or a retry
  /// replays the first instead of re-running against a used-up code.
  final _idempotencyKey = const Uuid().v4();

  /// The driver typed the amount themselves; stop overwriting it.
  bool _amountEdited = false;

  /// A partial payment: whatever is not collected stays on the customer's
  /// account (needs the agency's credit to be on).
  bool _onAccount = false;

  /// The balance the amount field was last filled from.
  double? _syncedBalance;
  bool _resending = false;
  String? _error;
  bool _prefilled = false;

  /// The error banner beside "Confirm delivery", scrolled into view on error.
  final _errorKey = GlobalKey();

  /// Testing only: the delivery code read back from the dev inbox.
  String? _devCode;

  /// Money the customer already paid online for this order (from the latest
  /// settlement answer): never to be collected again.
  double _paidOnline = 0;

  @override
  void initState() {
    super.initState();
    _loadDevCode();
    _amountController.addListener(() {
      // Rebuild the settlement hints as the driver types.
      if (mounted) setState(() {});
    });
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
      _delivered[line.cylinderTypeId] = line.quantityOrdered;
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
    LpgHaptics.warning();
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

  /// The empties to take back for one size, and the most that can be.
  ///
  /// [held] is what the customer was holding before this delivery, by size;
  /// that is the limit, and one empty per cylinder delivered is filled in.
  /// While it is `null` (not loaded) the limit is what is delivered here and
  /// nothing is filled in, so the server never refuses a number the driver
  /// did not enter.
  ({int value, int max}) _emptiesFor(
    String cylinderTypeId, {
    required Map<String, int>? held,
    required int delivered,
  }) {
    final max = held == null ? delivered : held[cylinderTypeId] ?? 0;
    final value = _empties[cylinderTypeId] ?? (held == null ? 0 : delivered);
    return (value: value.clamp(0, max), max: max);
  }

  /// The balance still to collect: the server's answer when there is one
  /// (it knows what was paid online), otherwise an estimate from the order.
  double? _balanceDue(OrderResponse order, DeliverySettlement? settlement) {
    if (settlement != null) return settlement.balanceDue;
    final payable = order.amountToPay;
    if (payable == null) return null;
    var orderedValue = 0.0;
    var deliveredValue = 0.0;
    var allDelivered = true;
    for (final line in order.lines) {
      final delivered = _delivered[line.cylinderTypeId] ?? 0;
      if (delivered != line.quantityOrdered) allDelivered = false;
      final price = line.unitPrice ?? 1;
      orderedValue += price * line.quantityOrdered;
      deliveredValue += price * delivered;
    }
    if (allDelivered || orderedValue == 0) return payable;
    return double.parse(
      (payable * deliveredValue / orderedValue).toStringAsFixed(2),
    );
  }

  /// Keeps "Amount collected" at what is due until the driver types their own
  /// figure; on credit it starts at nothing.
  void _syncAmount(double? balance, {required bool credit}) {
    if (_amountEdited || balance == null) return;
    final target = credit ? 0.0 : balance;
    if (_syncedBalance == target) return;
    _syncedBalance = target;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _amountEdited) return;
      _amountController.text = target.toStringAsFixed(2);
    });
  }

  /// Leaves the finished stop. The Deliveries tab keeps its own stack, so it
  /// is reset first: otherwise this screen would still be waiting there, and
  /// tapping Confirm again would hit a delivery code that is already used.
  void _leave() {
    StatefulNavigationShell.maybeOf(
      context,
    )?.goBranch(1, initialLocation: true);
    context.go('/');
  }

  Future<void> _submit(
    OrderResponse order, {
    required double? balanceDue,
    required Map<String, int> collected,
    required List<CollectedEmptyRequest> otherEmpties,
  }) async {
    if (_done || _submitting) return;
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
      // Nothing to collect (paid online in full): record that, not cash.
      final nothingDue = balanceDue != null && balanceDue <= 0;
      final amount = nothingDue
          ? 0.0
          : double.tryParse(_amountController.text.trim());
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
                  quantityDelivered: _delivered[line.cylinderTypeId]!,
                  quantityCollectedEmpty: collected[line.cylinderTypeId]!,
                ),
            ],
            otherEmpties: otherEmpties,
            otpCode: _otpController.text.trim(),
            gpsLat: position.latitude,
            gpsLng: position.longitude,
            paymentMethod: nothingDue && _paidOnline > 0
                ? 'online_gateway'
                : _method,
            // On credit nothing is handed over.
            amountCollected: _method == 'credit' ? 0.0 : amount,
            balanceOnAccount: _onAccount && _method != 'credit',
            idempotencyKey: _idempotencyKey,
            signatureBytes: signatureBytes,
            photoBytes: _photoBytes,
            dacCode: _dacController.text.trim().isEmpty
                ? null
                : _dacController.text.trim(),
          );
      if (!mounted) return;

      switch (outcome) {
        case DeliverFailed(:final message):
          // The refusal may be that the customer holds fewer empties than
          // this screen was told: read the figures again.
          ref.invalidate(heldEmptiesProvider(order.id));
          _showError(message);
        case DeliverSynced() || DeliverQueued():
          _done = true;
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
          _leave();
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
          final heldAsync = ref.watch(heldEmptiesProvider(order.id));
          final heldList = heldAsync.value;
          final held = heldList == null
              ? null
              : {for (final h in heldList) h.cylinderTypeId: h.quantityHeld};
          // The held figures carry the size names; without them, use the list
          // the van-load screen caches.
          final names = heldList == null
              ? ref.watch(cylinderTypeNamesProvider).value ??
                    const <String, String>{}
              : {
                  for (final h in heldList)
                    h.cylinderTypeId: h.cylinderTypeName,
                };
          final lineEmpties = {
            for (final line in order.lines)
              line.cylinderTypeId: _emptiesFor(
                line.cylinderTypeId,
                held: held,
                delivered: _delivered[line.cylinderTypeId] ?? 0,
              ),
          };
          // Sizes the customer holds that are not on this order.
          final otherSizes = [
            for (final h in heldList ?? const <HeldEmpties>[])
              if (!lineEmpties.containsKey(h.cylinderTypeId) &&
                  h.quantityHeld > 0)
                (
                  size: h,
                  empties: _emptiesFor(
                    h.cylinderTypeId,
                    held: held,
                    delivered: 0,
                  ),
                ),
          ];
          ref.watch(paymentMethodsProvider); // rebuild when it arrives
          final offered = _offeredMethods;
          final method = _method;
          final settlement = ref
              .watch(
                _settlementProvider((
                  orderId: order.id,
                  delivered: [
                    for (final e in _delivered.entries) '${e.key}:${e.value}',
                  ].join(','),
                )),
              )
              .value;
          _paidOnline = settlement?.paidOnline ?? 0;
          final balance = _balanceDue(order, settlement);
          final credit = method == 'credit';
          _syncAmount(balance, credit: credit);
          final nothingDue = balance != null && balance <= 0;
          final entered = double.tryParse(_amountController.text.trim()) ?? 0;
          final shortBy = balance == null || credit || nothingDue
              ? 0.0
              : balance - entered;
          final canCredit = offered.any((m) => m.code == 'credit');
          final settled = shortBy <= 0.5 || (_onAccount && canCredit);
          return ListView(
            padding: LpgSpacing.page,
            children: [
              const _Section(
                step: 1,
                icon: LpgIcons.cylinder,
                title: 'Cylinders',
              ),
              for (final line in order.lines)
                Padding(
                  padding: const EdgeInsets.only(bottom: LpgSpacing.sm),
                  child: _QuantityCard(
                    name: names[line.cylinderTypeId] ?? 'Cylinder',
                    note: held == null
                        ? 'Ordered: ${line.quantityOrdered}'
                        : 'Ordered: ${line.quantityOrdered} · '
                              '${_holding(held[line.cylinderTypeId] ?? 0)}',
                    delivered: (
                      value: _delivered[line.cylinderTypeId] ?? 0,
                      max: line.quantityOrdered,
                    ),
                    onDelivered: (v) =>
                        setState(() => _delivered[line.cylinderTypeId] = v),
                    empties: lineEmpties[line.cylinderTypeId]!,
                    onEmpties: (v) =>
                        setState(() => _empties[line.cylinderTypeId] = v),
                  ),
                ),
              for (final other in otherSizes)
                Padding(
                  padding: const EdgeInsets.only(bottom: LpgSpacing.sm),
                  child: _QuantityCard(
                    name: other.size.cylinderTypeName,
                    note:
                        'Not on this order · '
                        '${_holding(other.size.quantityHeld)}',
                    empties: other.empties,
                    onEmpties: (v) =>
                        setState(() => _empties[other.size.cylinderTypeId] = v),
                  ),
                ),
              if (held == null && !heldAsync.isLoading)
                const LpgBanner(
                  tone: LpgTone.info,
                  message:
                      "This customer's empties could not be checked. Enter "
                      'only what you take back; the server checks it when '
                      'the delivery is sent.',
                ),
              const _Section(step: 2, icon: LpgIcons.payment, title: 'Payment'),
              if (balance != null || (settlement?.paidOnline ?? 0) > 0)
                _SettlementCard(
                  payable: settlement?.payable ?? order.amountToPay,
                  paidOnline: settlement?.paidOnline ?? 0,
                  balanceDue: balance,
                ),
              if (nothingDue) ...[
                const SizedBox(height: LpgSpacing.sm),
                LpgBanner(
                  tone: LpgTone.success,
                  title: (settlement?.paidOnline ?? 0) > 0
                      ? 'Already paid online'
                      : 'Nothing to collect',
                  message: (settlement?.paidOnline ?? 0) > 0
                      ? 'The customer paid ${LpgFormat.currency(settlement!.paidOnline)} '
                            'online. Do not collect any cash.'
                      : 'There is no balance on this delivery.',
                ),
              ] else ...[
                if ((settlement?.paidOnline ?? 0) > 0) ...[
                  const SizedBox(height: LpgSpacing.sm),
                  LpgBanner(
                    tone: LpgTone.info,
                    title: 'Part paid online',
                    message:
                        '${LpgFormat.currency(settlement!.paidOnline)} was paid '
                        'online. Collect only the rest.',
                  ),
                ],
                const SizedBox(height: LpgSpacing.md),
                LpgDropdownField<String>(
                  value: method,
                  items: {for (final m in offered) m.code: m.label},
                  icons: _paymentMethodIcons,
                  onChanged: (v) {
                    if (v != null) {
                      setState(() {
                        _paymentMethod = v;
                        _syncedBalance = null;
                      });
                    }
                  },
                ),
                if (method == 'upi') ...[
                  const SizedBox(height: LpgSpacing.md),
                  _UpiQrPanel(orderId: widget.orderId),
                ],
                const SizedBox(height: LpgSpacing.md),
                if (!credit)
                  LpgTextField(
                    label: 'Amount collected',
                    prefixIcon: LpgIcons.rupee,
                    controller: _amountController,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    onChanged: (_) => _amountEdited = true,
                  ),
                if (credit && balance != null)
                  LpgBanner(
                    tone: LpgTone.info,
                    title: 'On credit',
                    message:
                        '${LpgFormat.currency(balance)} will go on the '
                        "customer's account. Nothing to collect.",
                  ),
                if (!credit && canCredit && shortBy > 0.5) ...[
                  const SizedBox(height: LpgSpacing.sm),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _onAccount,
                    onChanged: (v) => setState(() => _onAccount = v),
                    title: Text(
                      "Put ${LpgFormat.currency(shortBy)} on the customer's "
                      'account',
                    ),
                  ),
                ],
              ],
              const _Section(
                step: 3,
                icon: LpgIcons.lock,
                title: 'Delivery code',
              ),
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
              if (!settled) ...[
                LpgBanner(
                  tone: LpgTone.warning,
                  title: 'Payment not settled',
                  message:
                      '${LpgFormat.currency(shortBy)} is still to collect. '
                      'Collect it to complete the delivery, or choose On '
                      'credit if the customer pays later.',
                ),
                const SizedBox(height: LpgSpacing.smd),
              ],
              LpgButton(
                label: 'Complete delivery',
                icon: LpgIcons.check,
                expand: true,
                size: LpgButtonSize.large,
                isLoading: _submitting,
                onPressed: _submitting || _done || !settled
                    ? null
                    : () => _submit(
                        order,
                        balanceDue: balance,
                        collected: {
                          for (final e in lineEmpties.entries)
                            e.key: e.value.value,
                        },
                        otherEmpties: [
                          for (final other in otherSizes)
                            if (other.empties.value > 0)
                              CollectedEmptyRequest(
                                cylinderTypeId: other.size.cylinderTypeId,
                                quantity: other.empties.value,
                              ),
                        ],
                      ),
              ),
            ],
          );
        },
      ),
    );
  }

  /// Height of the signature pad and the photo preview.
  static const _padHeight = 160.0;

  static String _holding(int held) => held == 0
      ? 'no earlier empties to collect'
      : 'up to $held ${held == 1 ? 'empty' : 'empties'} to collect';
}

/// A form section heading with its icon.
class _Section extends StatelessWidget {
  const _Section({required this.icon, required this.title, this.step});

  final IconData icon;
  final String title;

  /// The step number (1-3) of the stop flow, when this heading starts one.
  final int? step;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Padding(
      padding: const EdgeInsets.only(top: LpgSpacing.lg, bottom: LpgSpacing.sm),
      child: Semantics(
        header: true,
        child: Row(
          children: [
            if (step case final n?) ...[
              ExcludeSemantics(
                child: Container(
                  width: 22,
                  height: 22,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: colors.actionPrimaryContainer,
                  ),
                  child: Text(
                    '$n',
                    style: context.lpgText.labelSmall?.copyWith(
                      color: colors.onActionPrimaryContainer,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: LpgSpacing.sm),
            ],
            Icon(icon, size: LpgSizes.iconSm, color: colors.textSecondary),
            const SizedBox(width: LpgSpacing.sm),
            Flexible(child: Text(title, style: context.lpgText.titleSmall)),
          ],
        ),
      ),
    );
  }
}

/// One cylinder size: what is delivered (sizes on the order) and the empties
/// taken back.
class _QuantityCard extends StatelessWidget {
  const _QuantityCard({
    required this.name,
    required this.note,
    required this.empties,
    required this.onEmpties,
    this.delivered,
    this.onDelivered,
  });

  final String name;
  final String note;

  /// `null` for a size that is not on the order.
  final ({int value, int max})? delivered;
  final ValueChanged<int>? onDelivered;

  final ({int value, int max}) empties;
  final ValueChanged<int> onEmpties;

  @override
  Widget build(BuildContext context) {
    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(name, style: context.lpgText.titleSmall),
          const SizedBox(height: LpgSpacing.xs),
          Text(note, style: context.lpgText.bodySmall),
          if (delivered case final quantity?) ...[
            const SizedBox(height: LpgSpacing.sm),
            _Stepper(
              label: 'Delivered',
              size: name,
              value: quantity.value,
              max: quantity.max,
              onChanged: onDelivered!,
            ),
          ],
          const SizedBox(height: LpgSpacing.sm),
          _Stepper(
            label: 'Empties collected',
            size: name,
            value: empties.value,
            max: empties.max,
            onChanged: onEmpties,
          ),
        ],
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({
    required this.label,
    required this.size,
    required this.value,
    required this.max,
    required this.onChanged,
  });

  final String label;

  /// The cylinder size, so a screen reader can tell the cards apart.
  final String size;
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
          semanticLabel: '$label, $size',
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

/// Amount due, already paid online, and what is left to collect.
class _SettlementCard extends StatelessWidget {
  const _SettlementCard({
    required this.payable,
    required this.paidOnline,
    required this.balanceDue,
  });

  final double? payable;
  final double paidOnline;
  final double? balanceDue;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    Widget row(String label, double? value, {bool strong = false}) => Row(
      children: [
        Expanded(
          child: Text(label, style: strong ? text.titleSmall : text.bodyMedium),
        ),
        Text(
          value == null ? '—' : LpgFormat.currency(value),
          style: strong ? text.titleSmall : text.bodyMedium,
        ),
      ],
    );
    return LpgCard(
      child: Column(
        children: [
          row('Amount due', payable),
          if (paidOnline > 0) ...[
            const SizedBox(height: LpgSpacing.xs),
            row('Paid online', -paidOnline),
          ],
          const Divider(),
          row('To collect now', balanceDue, strong: true),
        ],
      ),
    );
  }
}

typedef _SettlementKey = ({String orderId, String delivered});

/// `GET /orders/{id}/settlement` for the quantities currently entered. `null`
/// when it can't be reached (offline): the screen then estimates from the
/// cached order and the server applies the same rule when the delivery syncs.
final _settlementProvider = FutureProvider.autoDispose
    .family<DeliverySettlement?, _SettlementKey>((ref, key) async {
      final delivered = <String, int>{};
      for (final part in key.delivered.split(',')) {
        if (part.isEmpty) continue;
        final i = part.lastIndexOf(':');
        delivered[part.substring(0, i)] = int.parse(part.substring(i + 1));
      }
      final result = await ref
          .watch(orderApiProvider)
          .getSettlement(key.orderId, delivered: delivered);
      return switch (result) {
        Success(:final value) => value,
        _ => null,
      };
    });
