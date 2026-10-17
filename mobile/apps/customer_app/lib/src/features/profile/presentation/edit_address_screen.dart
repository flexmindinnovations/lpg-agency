import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maps/maps.dart';

import '../../../providers.dart';
import '../data/profile_provider.dart';
import 'widgets/address_form_fields.dart';

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
        final navigator = Navigator.of(context);
        navigator.pop();
        ref.invalidate(profileProvider);
        LpgFeedback.showToast(
          navigator.context,
          'Address updated successfully',
          tone: LpgTone.success,
        );
      },
      onFailure: (failure) => setState(() => _error = failure.message),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Edit Address')),
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
                  label: 'Save Changes',
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
