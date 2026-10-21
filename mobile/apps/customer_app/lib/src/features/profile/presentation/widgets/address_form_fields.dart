import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maps/maps.dart';

import 'location_picker_field.dart';

/// The address form shared by the add and edit address screens, so both
/// stay field-for-field identical. The screens own the controllers and the
/// save call; this only lays the fields out.
/// A validator that rejects an empty or blank field with [message].
FormFieldValidator<String> _required(String message) =>
    (value) => (value == null || value.trim().isEmpty) ? message : null;

class AddressFormFields extends ConsumerWidget {
  const AddressFormFields({
    super.key,
    required this.addressType,
    required this.onAddressTypeChanged,
    required this.line1,
    required this.line2,
    required this.landmark,
    required this.area,
    required this.city,
    required this.state,
    required this.pincode,
    required this.pinnedLocation,
    required this.onPinnedLocationChanged,
  });

  // 'home'/'work'/'other' would look natural here, but the backend's
  // Address domain object only accepts ("delivery", "billing", "both")
  // (domain/customer/customer.py:133) and rejects anything else with a 400.
  static const addressTypes = ['delivery', 'billing', 'both'];

  final String addressType;
  final ValueChanged<String> onAddressTypeChanged;
  final TextEditingController line1;
  final TextEditingController line2;
  final TextEditingController landmark;
  final TextEditingController area;
  final TextEditingController city;
  final TextEditingController state;
  final TextEditingController pincode;
  final LatLng? pinnedLocation;
  final ValueChanged<LatLng?> onPinnedLocationChanged;

  static const _gap = SizedBox(height: LpgSpacing.mdl);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const LpgFieldLabel('Address type'),
        LpgChoiceChips<String>(
          options: const {
            'delivery': 'Delivery',
            'billing': 'Billing',
            'both': 'Both',
          },
          icons: const {
            'delivery': LpgIcons.truck,
            'billing': LpgIcons.receipt,
            'both': LpgIcons.allDone,
          },
          selected: addressType,
          onSelected: (value) {
            if (value != null) onAddressTypeChanged(value);
          },
        ),
        const SizedBox(height: LpgSpacing.lg),
        LpgTextField(
          label: 'Address line 1',
          isRequired: true,
          prefixIcon: LpgIcons.location,
          controller: line1,
          textInputAction: TextInputAction.next,
          textCapitalization: TextCapitalization.words,
          autofillHints: const [AutofillHints.streetAddressLine1],
          validator: (value) =>
              value == null || value.isEmpty ? 'Required' : null,
        ),
        _gap,
        LpgTextField(
          label: 'Address line 2',
          controller: line2,
          textInputAction: TextInputAction.next,
          textCapitalization: TextCapitalization.words,
          autofillHints: const [AutofillHints.streetAddressLine2],
        ),
        _gap,
        LpgTextField(
          label: 'Landmark',
          controller: landmark,
          textInputAction: TextInputAction.next,
          textCapitalization: TextCapitalization.sentences,
        ),
        _gap,
        LpgTextField(
          label: 'Area',
          controller: area,
          textInputAction: TextInputAction.next,
          textCapitalization: TextCapitalization.words,
        ),
        _gap,
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: LpgTextField(
                label: 'City',
                isRequired: true,
                controller: city,
                validator: _required('Enter the city.'),
                textInputAction: TextInputAction.next,
                textCapitalization: TextCapitalization.words,
                autofillHints: const [AutofillHints.addressCity],
              ),
            ),
            const SizedBox(width: LpgSpacing.md),
            Expanded(
              child: LpgTextField(
                label: 'State',
                isRequired: true,
                controller: state,
                validator: _required('Enter the state.'),
                textInputAction: TextInputAction.next,
                textCapitalization: TextCapitalization.words,
                autofillHints: const [AutofillHints.addressState],
              ),
            ),
          ],
        ),
        _gap,
        LpgTextField(
          label: 'Pincode',
          isRequired: true,
          controller: pincode,
          validator: (value) => RegExp(r'^[1-9]\d{5}$').hasMatch(value ?? '')
              ? null
              : 'Enter the 6-digit pincode.',
          keyboardType: TextInputType.number,
          maxLength: 6,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          autofillHints: const [AutofillHints.postalCode],
        ),
        const SizedBox(height: LpgSpacing.lg),
        LocationPickerField(
          value: pinnedLocation,
          tileProvider: ref.watch(mapTileProviderProvider),
          onChanged: onPinnedLocationChanged,
        ),
      ],
    );
  }
}
