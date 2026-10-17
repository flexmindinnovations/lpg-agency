import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../providers.dart';
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
    final profileAsync = ref.watch(profileProvider);
    final cylinderTypesAsync = ref.watch(cylinderTypesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Order Gas Refill')),
      body: profileAsync.when(
        loading: () => const LpgLoadingIndicator(),
        error: (error, _) => LpgErrorState(
          message: 'Could not load your profile: $error',
          onRetry: () => ref.invalidate(profileProvider),
        ),
        data: (profile) {
          if (profile == null) {
            return const LpgEmptyState(
              icon: LpgIcons.userOff,
              message: 'Your profile has not loaded yet.',
            );
          }
          if (profile.addresses.isEmpty) {
            return LpgEmptyState(
              icon: LpgIcons.addLocation,
              title: 'Add a delivery address',
              message:
                  'You need a saved delivery address before placing an '
                  'order.',
              actionLabel: 'Add Address',
              actionIcon: LpgIcons.add,
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

          final sections = <Widget>[
            if (_errorMessage != null) ...[
              LpgBanner(tone: LpgTone.danger, message: _errorMessage!),
              const SizedBox(height: LpgSpacing.lg),
            ],
            const LpgFieldLabel('Cylinder Type'),
            cylinderTypesAsync.when(
              loading: () => const LinearProgressIndicator(),
              error: (error, _) => LpgBanner(
                tone: LpgTone.danger,
                message: 'Could not load cylinder types: $error',
              ),
              data: (types) {
                if (types.isEmpty) {
                  return const LpgBanner(
                    message: 'No cylinder types are available right now.',
                  );
                }
                _cylinderTypeId ??= types.first.id;
                return Column(
                  children: [
                    for (final type in types)
                      Padding(
                        padding: const EdgeInsets.only(bottom: LpgSpacing.sm),
                        child: _CylinderOption(
                          title: type.name,
                          subtitle: '${type.weightKg} kg',
                          selected: type.id == _cylinderTypeId,
                          onTap: () =>
                              setState(() => _cylinderTypeId = type.id),
                        ),
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgCard(
              variant: LpgCardVariant.outlined,
              padding: const EdgeInsets.symmetric(
                horizontal: LpgSpacing.md,
                vertical: LpgSpacing.smd,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Quantity', style: context.lpgText.titleSmall),
                        Text(
                          'Cylinders to deliver',
                          style: context.lpgText.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  LpgQuantityStepper(
                    value: _quantity,
                    min: 1,
                    onChanged: (v) => setState(() => _quantity = v),
                  ),
                ],
              ),
            ),
            const SizedBox(height: LpgSpacing.lg),
            LpgDropdownField<String?>(
              label: 'Delivery Address',
              prefixIcon: LpgIcons.location,
              value: _addressId,
              items: {
                for (final address in profile.addresses)
                  address.id:
                      '${LpgFormat.sentence(address.addressType)} — '
                      '${address.line1}'
                      '${address.isPrimary ? ' (Primary)' : ''}',
              },
              onChanged: (v) => setState(() => _addressId = v),
            ),
            const SizedBox(height: LpgSpacing.lg),
            const LpgFieldLabel('Requested Date'),
            _DateField(value: _requestedDate, onTap: () => _pickDate(context)),
            const SizedBox(height: LpgSpacing.lg),
            const LpgFieldLabel('Payment Method (optional)'),
            LpgChoiceChips<String>(
              options: _paymentMethods,
              icons: const {
                'cash': LpgIcons.cash,
                'upi': LpgIcons.wallet,
                'card': LpgIcons.payment,
                'online_gateway': LpgIcons.security,
              },
              selected: _paymentMethod,
              allowDeselect: true,
              onSelected: (v) => setState(() => _paymentMethod = v),
            ),
          ];

          return Column(
            children: [
              Expanded(
                child: ListView(
                  padding: LpgSpacing.page,
                  children: [
                    for (var i = 0; i < sections.length; i++)
                      LpgFadeSlideIn(index: i, child: sections[i]),
                  ],
                ),
              ),
              _SubmitBar(
                submitting: _submitting,
                onSubmit: () => _submit(profile),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// One selectable cylinder type: a card that fills with the primary tint
/// and shows a check when chosen.
class _CylinderOption extends StatelessWidget {
  const _CylinderOption({
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Semantics(
      selected: selected,
      inMutuallyExclusiveGroup: true,
      child: LpgCard(
        variant: selected ? LpgCardVariant.tonal : LpgCardVariant.outlined,
        padding: const EdgeInsets.all(LpgSpacing.smd),
        onTap: onTap,
        child: Row(
          children: [
            LpgIconBox(
              icon: LpgIcons.cylinder,
              tone: selected ? LpgTone.primary : LpgTone.neutral,
            ),
            const SizedBox(width: LpgSpacing.smd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: context.lpgText.titleSmall),
                  Text(subtitle, style: context.lpgText.bodySmall),
                ],
              ),
            ),
            AnimatedSwitcher(
              duration: LpgMotion.small(context),
              child: selected
                  ? Icon(
                      LpgIcons.successFilled,
                      key: const ValueKey('on'),
                      color: colors.actionPrimary,
                    )
                  : Icon(
                      LpgIcons.circle,
                      key: const ValueKey('off'),
                      color: colors.borderStrong,
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A read-only field that opens the date picker, styled like the text
/// fields around it.
class _DateField extends StatelessWidget {
  const _DateField({required this.value, required this.onTap});

  final DateTime value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Requested date, ${DateFormat('EEEE d MMMM yyyy').format(value)}',
      excludeSemantics: true,
      child: InkWell(
        borderRadius: BorderRadius.circular(LpgRadius.lg),
        onTap: onTap,
        child: InputDecorator(
          decoration: const InputDecoration(
            prefixIcon: Icon(LpgIcons.calendar, size: LpgSizes.iconMd),
            suffixIcon: Icon(LpgIcons.chevronDown),
          ),
          child: Text(
            DateFormat('EEE, d MMM yyyy').format(value),
            style: context.lpgText.bodyLarge,
          ),
        ),
      ),
    );
  }
}

/// The pinned footer holding the primary action, so "Place Order" is
/// always in reach however long the form scrolls.
class _SubmitBar extends StatelessWidget {
  const _SubmitBar({required this.submitting, required this.onSubmit});

  final bool submitting;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.card,
        border: Border(top: BorderSide(color: colors.borderDefault)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            LpgSpacing.mdl,
            LpgSpacing.smd,
            LpgSpacing.mdl,
            LpgSpacing.smd,
          ),
          child: LpgButton(
            label: 'Place Order',
            icon: LpgIcons.check,
            isLoading: submitting,
            expand: true,
            onPressed: onSubmit,
          ),
        ),
      ),
    );
  }
}
