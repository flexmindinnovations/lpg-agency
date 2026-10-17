import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';

import '../../../offline/delivery_mutations.dart';
import '../../../offline/pending_sync.dart';
import '../data/active_route_provider.dart';
import '../data/image_picker_provider.dart';
import '../data/location_sharing.dart';
import '../data/stop_order_provider.dart';

/// Mirrors the backend's `PaymentMethod`.
const _paymentMethods = <(String, String)>[
  ('cash', 'Cash'),
  ('upi', 'UPI'),
  ('card', 'Card'),
  ('online_gateway', 'Online'),
  ('credit', 'On credit'),
];

/// The proof-of-delivery capture: quantities, payment, the customer's
/// delivery OTP, a signature, a photo and a GPS stamp — then
/// `POST /orders/{id}/deliver`.
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
  Uint8List? _photoBytes;
  bool _submitting = false;
  String? _error;
  bool _prefilled = false;

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
    if (order.totalAmount != null) {
      _amountController.text = order.totalAmount!.toStringAsFixed(2);
    }
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
      final signatureBytes = await _signature.toPngBytes();
      if (signatureBytes == null || _photoBytes == null) {
        throw Exception('A signature and a photo are both required.');
      }
      if (_otpController.text.trim().isEmpty) {
        throw Exception('Enter the delivery code the customer received.');
      }
      final amount = double.tryParse(_amountController.text.trim());
      if (amount == null || amount < 0) {
        throw Exception('Enter a valid amount collected.');
      }

      final position = await ref
          .read(driverGeolocatorProvider)
          .currentPosition();

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
            paymentMethod: _paymentMethod,
            amountCollected: amount,
            signatureBytes: signatureBytes,
            photoBytes: _photoBytes!,
            dacCode: _dacController.text.trim().isEmpty
                ? null
                : _dacController.text.trim(),
          );
      if (!mounted) return;

      switch (outcome) {
        case DeliverFailed(:final message):
          setState(() => _error = message);
        case DeliverSynced() || DeliverQueued():
          ref.invalidate(activeRouteProvider);
          ref.invalidate(routeHistoryProvider);
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
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
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
          return ListView(
            padding: LpgSpacing.page,
            children: [
              if (_error != null) ...[
                LpgBanner(tone: LpgTone.danger, message: _error!),
                const SizedBox(height: LpgSpacing.sm),
              ],
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
              LpgChoiceChips<String>(
                options: {
                  for (final (value, label) in _paymentMethods) value: label,
                },
                icons: const {
                  'cash': LpgIcons.cash,
                  'upi': LpgIcons.wallet,
                  'card': LpgIcons.payment,
                  'online_gateway': LpgIcons.security,
                  'credit': LpgIcons.invoice,
                },
                selected: _paymentMethod,
                onSelected: (v) {
                  if (v != null) setState(() => _paymentMethod = v);
                },
              ),
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
                label: '',
                hintText: 'Code from the customer',
                prefixIcon: LpgIcons.number,
                controller: _otpController,
                keyboardType: TextInputType.number,
                autofillHints: const [AutofillHints.oneTimeCode],
              ),
              const SizedBox(height: LpgSpacing.smd),
              // Delivery Authentication Code (Phase 20 subsystem 4) — the
              // OMC's own separate code, distinct from the code above.
              // Optional: coverage is ~90%, not 100%, and it never gates
              // delivery.
              LpgTextField(
                label: '',
                hintText: 'OMC delivery code (DAC) — optional',
                prefixIcon: LpgIcons.verified,
                controller: _dacController,
                keyboardType: TextInputType.number,
              ),
              const _Section(
                icon: LpgIcons.signature,
                title: "Customer's signature",
              ),
              LpgCard(
                variant: LpgCardVariant.outlined,
                padding: EdgeInsets.zero,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
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
              const _Section(icon: LpgIcons.camera, title: 'Delivery photo'),
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
