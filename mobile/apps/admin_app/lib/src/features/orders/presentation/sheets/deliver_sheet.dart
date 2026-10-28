import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';

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

  // Proof of delivery is optional, as it is in the Driver App.
  final _signature = SignatureController(penStrokeWidth: 2);
  Uint8List? _photoBytes;

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
    _signature.dispose();
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

  Future<void> _pickPhoto() async {
    final XFile? file;
    try {
      file = await ImagePicker().pickImage(
        source: ImageSource.camera,
        imageQuality: 60,
      );
    } catch (_) {
      setState(() => _error = 'Could not open the camera.');
      return;
    }
    if (file == null) return;
    final bytes = await file.readAsBytes();
    if (mounted) setState(() => _photoBytes = bytes);
  }

  /// Stages the optional signature and photo; the blob refs go in the
  /// delivery request. Returns the failure message when an upload fails.
  Future<({String? signature, String? photo, String? error})> _uploadProof(
    String orderId,
  ) async {
    final api = ref.read(orderApiProvider);
    String? signatureRef;
    if (_signature.isNotEmpty) {
      final bytes = await _signature.toPngBytes();
      if (bytes != null) {
        final r = await api.uploadPodAttachment(
          orderId,
          bytes: bytes,
          filename: 'signature.png',
        );
        switch (r) {
          case Success<PodAttachmentResponse>(:final value):
            signatureRef = value.blobRef;
          case FailureResult<PodAttachmentResponse>(:final failure):
            return (signature: null, photo: null, error: failure.message);
        }
      }
    }
    String? photoRef;
    if (_photoBytes != null) {
      final r = await api.uploadPodAttachment(
        orderId,
        bytes: _photoBytes!,
        filename: 'delivery.jpg',
        contentType: 'image/jpeg',
      );
      switch (r) {
        case Success<PodAttachmentResponse>(:final value):
          photoRef = value.blobRef;
        case FailureResult<PodAttachmentResponse>(:final failure):
          return (signature: null, photo: null, error: failure.message);
      }
    }
    return (signature: signatureRef, photo: photoRef, error: null);
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
    final proof = await _uploadProof(order.id);
    if (!mounted) return;
    if (proof.error != null) {
      setState(() {
        _busy = false;
        _error = 'Could not upload the proof: ${proof.error}';
      });
      return;
    }
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
        signatureBlobRef: proof.signature,
        photoBlobRef: proof.photo,
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
          const SizedBox(height: LpgSpacing.md),
          Text("Customer's signature (optional)", style: text.titleSmall),
          const SizedBox(height: LpgSpacing.sm),
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
                    height: 140,
                    backgroundColor: context.lpgColors.card,
                  ),
                ),
                const Divider(height: 1),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: _busy ? null : _signature.clear,
                    icon: const Icon(LpgIcons.delete, size: LpgSizes.iconSm),
                    label: const Text('Clear'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          Text('Delivery photo (optional)', style: text.titleSmall),
          const SizedBox(height: LpgSpacing.sm),
          if (_photoBytes case final photo?) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(LpgRadius.xl),
              child: Image.memory(
                photo,
                height: 140,
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
            onPressed: _busy ? null : _pickPhoto,
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
