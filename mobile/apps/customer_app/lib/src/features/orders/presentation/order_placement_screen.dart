import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../providers.dart';
import '../../../widgets/form_field_widgets.dart';
import '../../profile/data/profile_provider.dart';
import '../data/cylinder_types_provider.dart';
import '../data/orders_provider.dart';

const _paymentMethods = <String, String>{
  'cash': 'Cash on Delivery',
  'upi': 'UPI',
  'card': 'Card',
  'online_gateway': 'Online Payment',
};

/// Real order-placement flow: cylinder type, quantity, delivery address,
/// requested date, and an optional payment preference, submitted as an
/// actual `CreateOrderRequest`. Replaces the old `OrderBottomSheet`, which
/// only ever collected a quantity and enqueued a payload
/// (`{quantity, cylinder_size_kg}`) that didn't match what the backend
/// needs and so could never produce a real order.
class OrderPlacementScreen extends ConsumerStatefulWidget {
  const OrderPlacementScreen({super.key});

  @override
  ConsumerState<OrderPlacementScreen> createState() =>
      _OrderPlacementScreenState();
}

class _OrderPlacementScreenState extends ConsumerState<OrderPlacementScreen> {
  String? _cylinderTypeId;
  int _quantity = 1;
  String? _addressId;
  DateTime _requestedDate = DateTime.now();
  String? _paymentMethod;
  bool _submitting = false;
  String? _errorMessage;

  Future<void> _pickDate(BuildContext context) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _requestedDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 60)),
    );
    if (picked != null) setState(() => _requestedDate = picked);
  }

  Future<void> _submit(CustomerResponse profile) async {
    if (_cylinderTypeId == null) {
      setState(() => _errorMessage = 'Please select a cylinder type.');
      return;
    }
    if (_addressId == null) {
      setState(() => _errorMessage = 'Please select a delivery address.');
      return;
    }

    final address = profile.addresses.firstWhere((a) => a.id == _addressId);
    final addressLine = [
      address.line1,
      address.line2,
      address.area,
      address.city,
      address.state,
      address.pincode,
    ].where((part) => part != null && part.isNotEmpty).join(', ');

    final request = CreateOrderRequest(
      branchId: profile.branchId,
      customerId: profile.id,
      addressId: address.id,
      deliveryAddress: DeliveryAddressPayload(
        addressLine: addressLine,
        latitude: address.latitude,
        longitude: address.longitude,
      ),
      bookingSource: 'mobile_app',
      requestedDate: _requestedDate,
      lines: [
        CreateOrderLineRequest(
          cylinderTypeId: _cylinderTypeId!,
          quantity: _quantity,
        ),
      ],
      paymentMethodPreference: _paymentMethod,
    );

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final result = await ref.read(orderApiProvider).createOrder(request);

    if (!mounted) return;
    setState(() => _submitting = false);

    result.when(
      onSuccess: (_) {
        // Pop *before* invalidating — matches the fix in
        // order_detail_screen.dart's cancel flow, where invalidating a
        // provider first and touching `context` afterwards hit a real
        // framework assertion crash live.
        final messenger = ScaffoldMessenger.of(context);
        Navigator.of(context).pop();
        ref.invalidate(ordersProvider);
        messenger.showSnackBar(
          const SnackBar(content: Text('Order placed successfully.')),
        );
      },
      onFailure: (failure) async {
        if (failure.errorCode == 'NETWORK_UNAVAILABLE') {
          // No connection — queue it through the sync engine instead of
          // just failing. SyncCoordinator._dispatch already knows how to
          // POST an 'order_gas' payload shaped like CreateOrderRequest.
          await ref
              .read(syncCoordinatorProvider)
              .enqueueOperation('order_gas', jsonEncode(request.toJson()));
          if (!mounted) return;
          final messenger = ScaffoldMessenger.of(context);
          Navigator.of(context).pop();
          messenger.showSnackBar(
            const SnackBar(
              content: Text(
                "You're offline — order queued and will be placed "
                'automatically once you reconnect.',
              ),
            ),
          );
          return;
        }
        setState(() => _errorMessage = failure.message);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final profileAsync = ref.watch(profileProvider);
    final cylinderTypesAsync = ref.watch(cylinderTypesProvider);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Order Gas Refill',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: profileAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => LpgEmptyState(
          icon: Icons.error_outline,
          message: 'Could not load your profile: $error',
        ),
        data: (profile) {
          if (profile == null) {
            return const LpgEmptyState(
              icon: Icons.person_off_outlined,
              message: 'Your profile has not loaded yet.',
            );
          }
          if (profile.addresses.isEmpty) {
            return LpgEmptyState(
              icon: Icons.location_off_outlined,
              message:
                  'You need a saved delivery address before placing an '
                  'order.',
              actionLabel: 'Add Address',
              onAction: () =>
                  context.push('/profile/addresses/new', extra: profile.id),
            );
          }

          // Default to the primary address / first cylinder type once
          // data is available, so the customer isn't forced to make a
          // choice that already has an obvious answer.
          _addressId ??= profile.addresses
              .firstWhere(
                (a) => a.isPrimary,
                orElse: () => profile.addresses.first,
              )
              .id;

          return Form(
            child: ListView(
              padding: const EdgeInsets.all(24.0),
              children: [
                if (_errorMessage != null) ...[
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: colors.statusDanger.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: colors.statusDanger.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.error_outline, color: colors.statusDanger),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: TextStyle(
                              color: colors.statusDanger,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ],

                const FieldLabel('Cylinder Type'),
                cylinderTypesAsync.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (error, _) => Text(
                    'Could not load cylinder types: $error',
                    style: TextStyle(color: colors.statusDanger),
                  ),
                  data: (types) {
                    if (types.isEmpty) {
                      return Text(
                        'No cylinder types are available right now.',
                        style: TextStyle(color: colors.textSecondary),
                      );
                    }
                    _cylinderTypeId ??= types.first.id;
                    return FormDropdownField<String?>(
                      value: _cylinderTypeId,
                      items: {
                        for (final type in types)
                          type.id: '${type.name} (${type.weightKg} kg)',
                      },
                      onChanged: (v) => setState(() => _cylinderTypeId = v),
                    );
                  },
                ),
                const SizedBox(height: 20),

                const FieldLabel('Quantity'),
                Row(
                  children: [
                    _QtyButton(
                      icon: Icons.remove,
                      onPressed: _quantity > 1
                          ? () => setState(() => _quantity--)
                          : null,
                      colors: colors,
                    ),
                    const SizedBox(width: 20),
                    Text(
                      '$_quantity',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                        color: colors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 20),
                    _QtyButton(
                      icon: Icons.add,
                      onPressed: () => setState(() => _quantity++),
                      colors: colors,
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                const FieldLabel('Delivery Address'),
                FormDropdownField<String?>(
                  value: _addressId,
                  items: {
                    for (final address in profile.addresses)
                      address.id:
                          '${address.addressType.toUpperCase()} — '
                          '${address.line1}'
                          '${address.isPrimary ? ' (Primary)' : ''}',
                  },
                  onChanged: (v) => setState(() => _addressId = v),
                ),
                const SizedBox(height: 20),

                const FieldLabel('Requested Date'),
                InkWell(
                  borderRadius: BorderRadius.circular(8),
                  onTap: () => _pickDate(context),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 14,
                    ),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: colors.borderDefault),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.calendar_today_outlined,
                          size: 18,
                          color: colors.textSecondary,
                        ),
                        const SizedBox(width: 12),
                        Text(
                          DateFormat('EEE, d MMM yyyy').format(_requestedDate),
                          style: TextStyle(color: colors.textPrimary),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                const FieldLabel('Payment Method (optional)'),
                FormDropdownField<String?>(
                  value: _paymentMethod,
                  items: _paymentMethods,
                  placeholder: 'No preference',
                  onChanged: (v) => setState(() => _paymentMethod = v),
                ),

                const SizedBox(height: 32),
                LpgButton(
                  label: 'Place Order',
                  isLoading: _submitting,
                  expand: true,
                  onPressed: () => _submit(profile),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _QtyButton extends StatelessWidget {
  const _QtyButton({
    required this.icon,
    required this.onPressed,
    required this.colors,
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final LpgColors colors;

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null;
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: colors.surfaceRaised,
          shape: BoxShape.circle,
          border: Border.all(
            color: disabled ? colors.borderDefault : colors.actionPrimary,
          ),
        ),
        child: Icon(
          icon,
          size: 18,
          color: disabled
              ? colors.textSecondary.withValues(alpha: 0.3)
              : colors.actionPrimary,
        ),
      ),
    );
  }
}
