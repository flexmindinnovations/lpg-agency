import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maps/maps.dart';

import '../../../providers.dart';
import '../data/profile_provider.dart';
import 'widgets/location_picker_field.dart';

/// Edits an existing saved address — mirrors `AddAddressScreen`'s form
/// exactly (same fields, same `UpdateCustomerAddressRequest`/
/// `AddCustomerAddressRequest` shape), pre-filled from [address] and
/// PUTting via `CustomerApi.updateAddress` instead of POSTing a new one.
class EditAddressScreen extends ConsumerStatefulWidget {
  const EditAddressScreen({
    super.key,
    required this.customerId,
    required this.address,
  });

  final String customerId;
  final CustomerAddressResponse address;

  @override
  ConsumerState<EditAddressScreen> createState() => _EditAddressScreenState();
}

class _EditAddressScreenState extends ConsumerState<EditAddressScreen> {
  final _formKey = GlobalKey<FormState>();
  late final _line1Controller = TextEditingController(
    text: widget.address.line1,
  );
  late final _line2Controller = TextEditingController(
    text: widget.address.line2 ?? '',
  );
  late final _landmarkController = TextEditingController(
    text: widget.address.landmark ?? '',
  );
  late final _areaController = TextEditingController(
    text: widget.address.area ?? '',
  );
  late final _cityController = TextEditingController(
    text: widget.address.city ?? '',
  );
  late final _stateController = TextEditingController(
    text: widget.address.state ?? '',
  );
  late final _pincodeController = TextEditingController(
    text: widget.address.pincode ?? '',
  );

  late String _addressType = widget.address.addressType.toLowerCase();
  late LatLng? _pinnedLocation =
      widget.address.latitude != null && widget.address.longitude != null
      ? LatLng(widget.address.latitude!, widget.address.longitude!)
      : null;
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
    final request = UpdateCustomerAddressRequest(
      line1: _line1Controller.text.trim(),
      line2: _line2Controller.text.trim().isEmpty
          ? null
          : _line2Controller.text.trim(),
      landmark: _landmarkController.text.trim().isEmpty
          ? null
          : _landmarkController.text.trim(),
      area: _areaController.text.trim().isEmpty
          ? null
          : _areaController.text.trim(),
      city: _cityController.text.trim().isEmpty
          ? null
          : _cityController.text.trim(),
      state: _stateController.text.trim().isEmpty
          ? null
          : _stateController.text.trim(),
      pincode: _pincodeController.text.trim().isEmpty
          ? null
          : _pincodeController.text.trim(),
      addressType: _addressType,
      latitude: _pinnedLocation?.latitude,
      longitude: _pinnedLocation?.longitude,
    );

    final result = await api.updateAddress(
      widget.customerId,
      widget.address.id,
      request,
    );

    if (!mounted) return;
    setState(() => _isLoading = false);
    result.when(
      onSuccess: (_) {
        // Pop before invalidating -- matches the crash-fix pattern
        // elsewhere in this app (order_detail_screen.dart's cancel flow):
        // invalidate only after the screen that would otherwise be
        // rebuilt mid-navigation is off the stack.
        final messenger = ScaffoldMessenger.of(context);
        Navigator.of(context).pop();
        ref.invalidate(profileProvider);
        messenger.showSnackBar(
          const SnackBar(content: Text('Address updated successfully')),
        );
      },
      onFailure: (failure) => setState(() => _error = failure.message),
    );
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
          'Edit Address',
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
                          color: colors.statusDanger.withValues(alpha: 0.1),
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
                        ButtonSegment(
                          value: 'delivery',
                          label: Text('Delivery'),
                          icon: Icon(Icons.local_shipping_outlined),
                        ),
                        ButtonSegment(
                          value: 'billing',
                          label: Text('Billing'),
                          icon: Icon(Icons.receipt_long_outlined),
                        ),
                        ButtonSegment(
                          value: 'both',
                          label: Text('Both'),
                          icon: Icon(Icons.done_all),
                        ),
                      ],
                      selected: {_addressType},
                      onSelectionChanged: (Set<String> newSelection) {
                        setState(() {
                          _addressType = newSelection.first;
                        });
                      },
                    ),
                    const SizedBox(height: 24),

                    LpgTextField(
                      label: 'Address Line 1*',
                      controller: _line1Controller,
                      validator: (value) =>
                          value == null || value.isEmpty ? 'Required' : null,
                    ),
                    const SizedBox(height: 20),
                    LpgTextField(
                      label: 'Address Line 2',
                      controller: _line2Controller,
                    ),
                    const SizedBox(height: 20),
                    LpgTextField(
                      label: 'Landmark',
                      controller: _landmarkController,
                    ),
                    const SizedBox(height: 20),
                    LpgTextField(label: 'Area', controller: _areaController),
                    const SizedBox(height: 20),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: LpgTextField(
                            label: 'City',
                            controller: _cityController,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: LpgTextField(
                            label: 'State',
                            controller: _stateController,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    LpgTextField(
                      label: 'Pincode',
                      controller: _pincodeController,
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 24),
                    LocationPickerField(
                      value: _pinnedLocation,
                      tileProvider: ref.watch(mapTileProviderProvider),
                      onChanged: (loc) => setState(() => _pinnedLocation = loc),
                    ),
                    const SizedBox(height: 40),
                    LpgButton(
                      label: 'Save Changes',
                      onPressed: _save,
                      isLoading: _isLoading,
                      expand: true,
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
