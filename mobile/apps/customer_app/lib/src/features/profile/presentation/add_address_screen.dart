import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maps/maps.dart';

import '../../../providers.dart';
import '../data/profile_provider.dart';
import 'widgets/address_form_fields.dart';

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

  // See AddressFormFields.addressTypes for why it isn't 'home'.
  String _addressType = AddressFormFields.addressTypes.first;
  LatLng? _pinnedLocation;
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

    final result = await api.addCustomerAddress(widget.customerId, request);

    if (!mounted) return;
    setState(() => _isLoading = false);
    result.when(
      onSuccess: (_) {
        // Pop before invalidating, so the profile list rebuilds only once
        // this screen is off the stack; toast on the screen underneath.
        final navigator = Navigator.of(context);
        navigator.pop();
        ref.invalidate(profileProvider);
        LpgFeedback.showToast(
          navigator.context,
          'Address added successfully',
          tone: LpgTone.success,
        );
      },
      onFailure: (failure) => setState(() => _error = failure.message),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add New Address')),
      body: SingleChildScrollView(
        padding: LpgSpacing.page,
        child: Form(
          key: _formKey,
          child: AutofillGroup(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_error != null) ...[
                  LpgBanner(tone: LpgTone.danger, message: _error!),
                  const SizedBox(height: LpgSpacing.lg),
                ],
                AddressFormFields(
                  addressType: _addressType,
                  onAddressTypeChanged: (type) =>
                      setState(() => _addressType = type),
                  line1: _line1Controller,
                  line2: _line2Controller,
                  landmark: _landmarkController,
                  area: _areaController,
                  city: _cityController,
                  state: _stateController,
                  pincode: _pincodeController,
                  pinnedLocation: _pinnedLocation,
                  onPinnedLocationChanged: (loc) =>
                      setState(() => _pinnedLocation = loc),
                ),
                const SizedBox(height: LpgSpacing.xl),
                LpgButton(
                  label: 'Save Address',
                  icon: LpgIcons.check,
                  onPressed: _save,
                  isLoading: _isLoading,
                  expand: true,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
