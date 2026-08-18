import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../providers.dart';
import '../data/profile_provider.dart';

class AddAddressScreen extends ConsumerStatefulWidget {
  const AddAddressScreen({super.key, required this.customerId});

  final String customerId;

  @override
  ConsumerState<AddAddressScreen> createState() => _AddAddressScreenState();
}

class _AddAddressScreenState extends ConsumerState<AddAddressScreen> {
  final _formKey = GlobalKey<FormState>();
  final _line1Controller = TextEditingController();
  final _line2Controller = TextEditingController();
  final _landmarkController = TextEditingController();
  final _areaController = TextEditingController();
  final _cityController = TextEditingController();
  final _stateController = TextEditingController();
  final _pincodeController = TextEditingController();
  
  String _addressType = 'home';
  bool _isLoading = false;
  String? _error;

  @override
  void dispose() {
    _line1Controller.dispose();
    _line2Controller.dispose();
    _landmarkController.dispose();
    _areaController.dispose();
    _cityController.dispose();
    _stateController.dispose();
    _pincodeController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final api = ref.read(customerApiProvider);
    final request = AddCustomerAddressRequest(
      line1: _line1Controller.text.trim(),
      line2: _line2Controller.text.trim().isEmpty ? null : _line2Controller.text.trim(),
      landmark: _landmarkController.text.trim().isEmpty ? null : _landmarkController.text.trim(),
      area: _areaController.text.trim().isEmpty ? null : _areaController.text.trim(),
      city: _cityController.text.trim().isEmpty ? null : _cityController.text.trim(),
      state: _stateController.text.trim().isEmpty ? null : _stateController.text.trim(),
      pincode: _pincodeController.text.trim().isEmpty ? null : _pincodeController.text.trim(),
      addressType: _addressType,
    );

    final result = await api.addCustomerAddress(widget.customerId, request);
    
    if (mounted) {
      setState(() => _isLoading = false);
      result.when(
        onSuccess: (data) {
          ref.invalidate(profileProvider);
          context.pop();
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Address added successfully')),
          );
        },
        onFailure: (failure) {
          setState(() => _error = failure.message);
        },
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Add New Address',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_error != null) ...[
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: colors.statusDanger.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: colors.statusDanger),
                        ),
                        child: Text(
                          _error!,
                          style: TextStyle(color: colors.statusDanger),
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],
                    
                    Text('Address Type', style: theme.textTheme.labelLarge),
                    const SizedBox(height: 8),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(value: 'home', label: Text('Home'), icon: Icon(Icons.home)),
                        ButtonSegment(value: 'work', label: Text('Work'), icon: Icon(Icons.business)),
                        ButtonSegment(value: 'other', label: Text('Other'), icon: Icon(Icons.location_on)),
                      ],
                      selected: {_addressType},
                      onSelectionChanged: (Set<String> newSelection) {
                        setState(() {
                          _addressType = newSelection.first;
                        });
                      },
                    ),
                    const SizedBox(height: 24),

                    TextFormField(
                      controller: _line1Controller,
                      decoration: const InputDecoration(labelText: 'Address Line 1*'),
                      validator: (value) => value == null || value.isEmpty ? 'Required' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _line2Controller,
                      decoration: const InputDecoration(labelText: 'Address Line 2'),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _landmarkController,
                      decoration: const InputDecoration(labelText: 'Landmark'),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _areaController,
                      decoration: const InputDecoration(labelText: 'Area'),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _cityController,
                            decoration: const InputDecoration(labelText: 'City'),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: TextFormField(
                            controller: _stateController,
                            decoration: const InputDecoration(labelText: 'State'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _pincodeController,
                      decoration: const InputDecoration(labelText: 'Pincode'),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 32),
                    ElevatedButton(
                      onPressed: _save,
                      child: const Text('Save Address'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
