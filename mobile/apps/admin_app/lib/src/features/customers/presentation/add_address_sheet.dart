import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../domain/customer_rules.dart';

/// Adds another address to a customer: where to deliver, or bill. Pops
/// `true` once saved.
class AddAddressSheet extends ConsumerStatefulWidget {
  const AddAddressSheet({super.key, required this.customerId});

  final String customerId;

  @override
  ConsumerState<AddAddressSheet> createState() => _AddAddressSheetState();
}

class _AddAddressSheetState extends ConsumerState<AddAddressSheet> {
  final _line1 = TextEditingController();
  final _area = TextEditingController();
  final _landmark = TextEditingController();
  final _city = TextEditingController();
  final _pincode = TextEditingController();
  String _type = 'delivery';
  String? _state;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_line1, _area, _landmark, _city, _pincode]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _optional(TextEditingController c) {
    final v = c.text.trim();
    return v.isEmpty ? null : v;
  }

  Future<void> _submit() async {
    final String? problem;
    if (_line1.text.trim().isEmpty) {
      problem = 'Enter the address.';
    } else if (_city.text.trim().isEmpty) {
      problem = 'Enter the city.';
    } else if (!isValidPincode(_pincode.text)) {
      problem = 'Enter the 6-digit PIN code.';
    } else {
      problem = null;
    }
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(customerApiProvider)
        .addCustomerAddress(
          widget.customerId,
          AddCustomerAddressRequest(
            line1: _line1.text.trim(),
            area: _optional(_area),
            landmark: _optional(_landmark),
            city: _city.text.trim(),
            state: _state,
            pincode: _pincode.text.trim(),
            addressType: _type,
          ),
        );
    if (!mounted) return;
    switch (result) {
      case Success<String>():
        Navigator.of(context).pop(true);
      case FailureResult<String>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgTextField(
            label: 'House, building and street',
            isRequired: true,
            controller: _line1,
            textCapitalization: TextCapitalization.words,
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Area (optional)',
            controller: _area,
            textCapitalization: TextCapitalization.words,
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Landmark (optional)',
            controller: _landmark,
            textCapitalization: TextCapitalization.words,
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'City',
            isRequired: true,
            controller: _city,
            textCapitalization: TextCapitalization.words,
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgDropdownField<String>(
            label: 'State (optional)',
            prefixIcon: LpgIcons.map,
            placeholder: 'Choose the state',
            value: _state ?? '',
            items: {for (final s in indianStates) s: s},
            onChanged: _busy ? null : (v) => setState(() => _state = v),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'PIN code',
            isRequired: true,
            controller: _pincode,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(6),
            ],
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgChoiceChips<String>(
            options: const {
              'delivery': 'Delivery',
              'billing': 'Billing',
              'both': 'Both',
            },
            selected: _type,
            onSelected: (v) {
              if (!_busy && v != null) setState(() => _type = v);
            },
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Save address',
            icon: LpgIcons.check,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}
