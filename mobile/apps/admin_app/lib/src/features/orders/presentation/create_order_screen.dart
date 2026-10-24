// Admin Order Placement Screen
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../providers.dart';
import '../data/orders_provider.dart';

class CreateOrderScreen extends ConsumerStatefulWidget {
  const CreateOrderScreen({super.key});

  @override
  ConsumerState<CreateOrderScreen> createState() => _CreateOrderScreenState();
}

class _CreateOrderScreenState extends ConsumerState<CreateOrderScreen> {
  final _customerIdController = TextEditingController();
  final _addressIdController = TextEditingController();
  final _branchIdController = TextEditingController();
  final _quantityController = TextEditingController(text: '1');

  String? _selectedCylinderTypeId;
  bool _submitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _customerIdController.dispose();
    _addressIdController.dispose();
    _branchIdController.dispose();
    _quantityController.dispose();
    super.dispose();
  }

  Future<void> _submitOrder() async {
    final customerId = _customerIdController.text.trim();
    final addressId = _addressIdController.text.trim();
    final branchId = _branchIdController.text.trim();
    final quantity = int.tryParse(_quantityController.text.trim()) ?? 1;

    if (customerId.isEmpty || addressId.isEmpty || branchId.isEmpty || _selectedCylinderTypeId == null) {
      setState(() => _errorMessage = 'Please fill in Customer ID, Address ID, Branch ID, and select Cylinder Type.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final orderApi = ref.read(orderApiProvider);
    final request = CreateOrderRequest(
      branchId: branchId,
      customerId: customerId,
      addressId: addressId,
      deliveryAddress: const DeliveryAddressPayload(
        addressLine: 'Admin Placement',
      ),
      bookingSource: 'phone',
      requestedDate: DateTime.now(),
      lines: [
        CreateOrderLineRequest(
          cylinderTypeId: _selectedCylinderTypeId!,
          quantity: quantity,
        ),
      ],
    );

    final result = await orderApi.createOrder(request);

    if (!mounted) return;

    result.when(
      onSuccess: (_) {
        LpgFeedback.showToast(context, 'Order created successfully');
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
    final text = context.lpgText;

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
              Text('Customer & Branch Details', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                controller: _customerIdController,
                label: 'Customer ID (UUID)',
                hintText: 'e.g. 550e8400-e29b-41d4-a716-446655440000',
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                controller: _branchIdController,
                label: 'Branch ID (UUID)',
                hintText: 'e.g. 123e4567-e89b-12d3-a456-426614174000',
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                controller: _addressIdController,
                label: 'Delivery Address ID (UUID)',
                hintText: 'e.g. 123e4567-e89b-12d3-a456-426614174000',
              ),
              const SizedBox(height: LpgSpacing.lg),
              Text('Cylinder & Quantity', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                controller: _quantityController,
                label: 'Quantity',
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                label: 'Cylinder Type ID',
                hintText: 'Enter cylinder type UUID',
                onChanged: (val) => _selectedCylinderTypeId = val.trim(),
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
