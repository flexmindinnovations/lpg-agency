import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';

import '../../../api_provider.dart';
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

      final orderApi = ref.read(orderApiProvider);
      final position = await ref
          .read(driverGeolocatorProvider)
          .currentPosition();

      final sig = _unwrap(
        await orderApi.uploadPodAttachment(
          order.id,
          bytes: signatureBytes,
          filename: 'signature.png',
        ),
      );
      final photo = _unwrap(
        await orderApi.uploadPodAttachment(
          order.id,
          bytes: _photoBytes!,
          filename: 'delivery.jpg',
          contentType: 'image/jpeg',
        ),
      );

      final result = await orderApi.deliverOrder(
        order.id,
        DeliverOrderRequest(
          lines: [
            for (final line in order.lines)
              DeliveredLineRequest(
                cylinderTypeId: line.cylinderTypeId,
                quantityDelivered: _quantities[line.cylinderTypeId]!.$1,
                quantityCollectedEmpty: _quantities[line.cylinderTypeId]!.$2,
              ),
          ],
          otpCode: _otpController.text.trim(),
          proofOfDelivery: ProofOfDeliverySubmission(
            signatureBlobRef: sig.blobRef,
            photoBlobRef: photo.blobRef,
            gpsLat: position.latitude,
            gpsLng: position.longitude,
            paymentMethod: _paymentMethod,
            amountCollected: amount,
          ),
        ),
      );

      result.when(
        onSuccess: (_) {
          ref.invalidate(activeRouteProvider);
          ref.invalidate(routeHistoryProvider);
          if (!mounted) return;
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('Delivery recorded.')));
          // Back to the route view rather than the stop detail: a delivered
          // order drops out of the driver's visibility (and their last stop
          // completes the route), so popping to `StopDetailScreen` would
          // strand them on a "stop not found" error.
          context.go('/');
        },
        onFailure: (failure) => setState(() => _error = failure.message),
      );
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  T _unwrap<T>(Result<T> result) => result.when(
    onSuccess: (v) => v,
    onFailure: (f) => throw Exception(f.message),
  );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final orderAsync = ref.watch(stopOrderProvider(widget.orderId));

    return Scaffold(
      appBar: AppBar(title: const Text('Record delivery')),
      body: orderAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Could not load this stop.\n$err',
          icon: Icons.error_outline,
        ),
        data: (order) {
          _prefill(order);
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_error != null) ...[
                _ErrorBanner(message: _error!),
                const SizedBox(height: 16),
              ],
              _section('Cylinders'),
              for (final line in order.lines)
                _QuantityRow(
                  ordered: line.quantityOrdered,
                  delivered: _quantities[line.cylinderTypeId]?.$1 ?? 0,
                  collected: _quantities[line.cylinderTypeId]?.$2 ?? 0,
                  onChanged: (d, c) =>
                      setState(() => _quantities[line.cylinderTypeId] = (d, c)),
                ),
              const SizedBox(height: 24),
              _section('Payment'),
              DropdownButtonFormField<String>(
                initialValue: _paymentMethod,
                decoration: const InputDecoration(labelText: 'Method'),
                items: [
                  for (final (value, label) in _paymentMethods)
                    DropdownMenuItem(value: value, child: Text(label)),
                ],
                onChanged: (v) => setState(() => _paymentMethod = v!),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _amountController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Amount collected (₹)',
                ),
              ),
              const SizedBox(height: 24),
              _section('Delivery code'),
              TextField(
                controller: _otpController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Code from the customer',
                ),
              ),
              const SizedBox(height: 24),
              _section("Customer's signature"),
              DecoratedBox(
                decoration: BoxDecoration(
                  border: Border.all(color: colors.borderDefault),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    Signature(
                      controller: _signature,
                      height: 160,
                      backgroundColor: colors.surfaceBase,
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: _signature.clear,
                        child: const Text('Clear'),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              _section('Delivery photo'),
              if (_photoBytes != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.memory(
                    _photoBytes!,
                    height: 160,
                    width: double.infinity,
                    fit: BoxFit.cover,
                  ),
                ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _pickPhoto,
                icon: const Icon(Icons.camera_alt_outlined),
                label: Text(_photoBytes == null ? 'Take a photo' : 'Retake'),
              ),
              const SizedBox(height: 32),
              LpgButton(
                label: 'Confirm delivery',
                expand: true,
                isLoading: _submitting,
                onPressed: _submitting ? null : () => _submit(order),
              ),
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }

  Widget _section(String title) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Text(
      title,
      style: Theme.of(
        context,
      ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
    ),
  );
}

class _QuantityRow extends StatelessWidget {
  const _QuantityRow({
    required this.ordered,
    required this.delivered,
    required this.collected,
    required this.onChanged,
  });

  final int ordered;
  final int delivered;
  final int collected;
  final void Function(int delivered, int collected) onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Ordered: $ordered',
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          _Stepper(
            label: 'Delivered',
            value: delivered,
            max: ordered,
            onChanged: (v) => onChanged(v, collected.clamp(0, v)),
          ),
          _Stepper(
            label: 'Empties collected',
            value: collected,
            max: delivered,
            onChanged: (v) => onChanged(delivered, v),
          ),
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
        Expanded(child: Text(label)),
        IconButton(
          onPressed: value > 0 ? () => onChanged(value - 1) : null,
          icon: const Icon(Icons.remove_circle_outline),
        ),
        SizedBox(width: 24, child: Text('$value', textAlign: TextAlign.center)),
        IconButton(
          onPressed: value < max ? () => onChanged(value + 1) : null,
          icon: const Icon(Icons.add_circle_outline),
        ),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colors.statusDanger.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.statusDanger),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: colors.statusDanger),
          const SizedBox(width: 12),
          Expanded(
            child: Text(message, style: TextStyle(color: colors.statusDanger)),
          ),
        ],
      ),
    );
  }
}
