import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../data/orders_provider.dart';

class CreateOrderScreen extends ConsumerStatefulWidget {
  const CreateOrderScreen({super.key});

  @override
  ConsumerState<CreateOrderScreen> createState() => _CreateOrderScreenState();
}

class _CreateOrderScreenState extends ConsumerState<CreateOrderScreen> {
  CustomerResponse? _selectedCustomer;
  CustomerAddressResponse? _selectedAddress;
  String? _selectedCylinderTypeId;
  final _quantityController = TextEditingController(text: '1');

  bool _submitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _quantityController.dispose();
    super.dispose();
  }

  Future<void> _submitOrder() async {
    final customer = _selectedCustomer;
    final address = _selectedAddress;
    final cylinderTypeId = _selectedCylinderTypeId;
    final quantity = int.tryParse(_quantityController.text.trim()) ?? 1;

    if (customer == null || address == null || cylinderTypeId == null) {
      setState(() => _errorMessage = 'Please select a Customer, Delivery Address, and Cylinder Type.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final orderApi = ref.read(orderApiProvider);
    final request = CreateOrderRequest(
      branchId: customer.branchId,
      customerId: customer.id,
      addressId: address.id,
      deliveryAddress: DeliveryAddressPayload(
        addressLine: '${address.line1}, ${address.city ?? ''}',
      ),
      bookingSource: 'phone',
      requestedDate: DateTime.now(),
      lines: [
        CreateOrderLineRequest(
          cylinderTypeId: cylinderTypeId,
          quantity: quantity,
        ),
      ],
    );

    final result = await orderApi.createOrder(request);

    if (!mounted) return;

    result.when(
      onSuccess: (_) {
        LpgFeedback.showToast(context, 'Order placed successfully on behalf of ${customer.fullName}');
        ref.invalidate(adminOrdersProvider(1));
        context.pop();
      },
      onFailure: (failure) {
        setState(() {
          _submitting = false;
          _errorMessage = failure.message;
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final customersAsync = ref.watch(availableCustomersProvider);
    final cylindersAsync = ref.watch(cylinderCatalogProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Create Order on Behalf')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: LpgSpacing.page,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_errorMessage != null) ...[
                LpgBanner(message: _errorMessage!, tone: LpgTone.danger),
                const SizedBox(height: LpgSpacing.md),
              ],

              Text('Customer Selection', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.sm),

              customersAsync.when(
                loading: () => const LpgSkeleton(height: 56),
                error: (err, _) => LpgErrorState(
                  message: errorMessage(err),
                  onRetry: () => ref.invalidate(availableCustomersProvider),
                ),
                data: (page) => DropdownButtonFormField<CustomerResponse>(
                  decoration: const InputDecoration(
                    labelText: 'Select Customer',
                    border: OutlineInputBorder(),
                  ),
                  initialValue: _selectedCustomer,
                  items: page.items.map((cust) {
                    return DropdownMenuItem(
                      value: cust,
                      child: Text('${cust.fullName} (${cust.phoneNumber})'),
                    );
                  }).toList(),
                  onChanged: (cust) {
                    setState(() {
                      _selectedCustomer = cust;
                      _selectedAddress = cust?.addresses.firstOrNull;
                    });
                  },
                ),
              ),

              const SizedBox(height: LpgSpacing.lg),

              if (_selectedCustomer != null) ...[
                Text('Delivery Address', style: text.titleMedium),
                const SizedBox(height: LpgSpacing.sm),
                if (_selectedCustomer!.addresses.isEmpty)
                  Text(
                    'No saved addresses for this customer.',
                    style: text.bodyMedium?.copyWith(color: colors.statusDanger),
                  )
                else
                  DropdownButtonFormField<CustomerAddressResponse>(
                    decoration: const InputDecoration(
                      labelText: 'Select Delivery Address',
                      border: OutlineInputBorder(),
                    ),
                    initialValue: _selectedAddress,
                    items: _selectedCustomer!.addresses.map((addr) {
                      return DropdownMenuItem(
                        value: addr,
                        child: Text('${addr.line1}, ${addr.city ?? ''}'),
                      );
                    }).toList(),
                    onChanged: (addr) {
                      setState(() => _selectedAddress = addr);
                    },
                  ),
                const SizedBox(height: LpgSpacing.lg),
              ],

              Text('Product & Quantity', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.sm),

              cylindersAsync.when(
                loading: () => const LpgSkeleton(height: 56),
                error: (err, _) => LpgErrorState(
                  message: errorMessage(err),
                  onRetry: () => ref.invalidate(cylinderCatalogProvider),
                ),
                data: (cylinders) => DropdownButtonFormField<String>(
                  decoration: const InputDecoration(
                    labelText: 'Select Cylinder Type',
                    border: OutlineInputBorder(),
                  ),
                  initialValue: _selectedCylinderTypeId,
                  items: cylinders.map((cyl) {
                    return DropdownMenuItem(
                      value: cyl.id,
                      child: Text('${cyl.name} (${cyl.weightKg} kg)'),
                    );
                  }).toList(),
                  onChanged: (val) {
                    setState(() => _selectedCylinderTypeId = val);
                  },
                ),
              ),

              const SizedBox(height: LpgSpacing.md),

              LpgTextField(
                controller: _quantityController,
                label: 'Quantity',
                keyboardType: TextInputType.number,
              ),

              const SizedBox(height: LpgSpacing.xxl),

              LpgButton(
                label: 'Place Order',
                isLoading: _submitting,
                onPressed: _submitting ? null : _submitOrder,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
