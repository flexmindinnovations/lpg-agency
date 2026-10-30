import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../providers.dart';
import '../../../shared/customer_types.dart';
import '../../fleet/data/fleet_providers.dart';
import '../../fleet/domain/fleet_rules.dart';
import '../domain/customer_rules.dart';

/// Registers a customer who booked by phone or walked in: who they are, how
/// to reach them and where to deliver. They can book straight away; the
/// office approves them later, which gives them a consumer number. Pops the
/// new [CustomerResponse].
class AddCustomerScreen extends ConsumerStatefulWidget {
  const AddCustomerScreen({super.key});

  @override
  ConsumerState<AddCustomerScreen> createState() => _AddCustomerScreenState();
}

class _AddCustomerScreenState extends ConsumerState<AddCustomerScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _contact = TextEditingController();
  final _phone = TextEditingController();
  final _altPhone = TextEditingController();
  final _email = TextEditingController();
  final _gstin = TextEditingController();
  final _line1 = TextEditingController();
  final _area = TextEditingController();
  final _landmark = TextEditingController();
  final _city = TextEditingController();
  final _pincode = TextEditingController();

  String _type = 'domestic';
  String? _branchId;
  String? _state;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [
      _name,
      _contact,
      _phone,
      _altPhone,
      _email,
      _gstin,
      _line1,
      _area,
      _landmark,
      _city,
      _pincode,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _required(String? v, String message) =>
      (v == null || v.trim().isEmpty) ? message : null;

  String? _optional(TextEditingController c) {
    final v = c.text.trim();
    return v.isEmpty ? null : v;
  }

  Future<void> _submit(List<FleetBranch> branches) async {
    if (!(_form.currentState?.validate() ?? false)) {
      setState(() => _error = 'Check the fields marked in red.');
      return;
    }
    final branchId =
        _branchId ?? (branches.length == 1 ? branches.first.id : null);
    if (branchId == null) {
      setState(() => _error = 'Choose the branch this customer belongs to.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final business = isBusinessCustomer(_type);
    final alt = _altPhone.text.trim();
    final result = await ref
        .read(customerApiProvider)
        .registerCustomer(
          RegisterCustomerRequest(
            branchId: branchId,
            fullName: _name.text.trim(),
            phoneNumber: normalizeMobile(_phone.text)!,
            customerType: _type,
            contactPerson: business ? _optional(_contact) : null,
            alternateMobile: alt.isEmpty ? null : normalizeMobile(alt),
            email: _optional(_email),
            gstin: business && _gstin.text.trim().isNotEmpty
                ? tidyGstin(_gstin.text)
                : null,
            address: AddCustomerAddressRequest(
              line1: _line1.text.trim(),
              area: _optional(_area),
              landmark: _optional(_landmark),
              city: _city.text.trim(),
              state: _state,
              pincode: _pincode.text.trim(),
            ),
          ),
        );
    if (!mounted) return;
    switch (result) {
      case Success<CustomerResponse>(:final value):
        context.pop(value);
      case FailureResult<CustomerResponse>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final branches = ref.watch(fleetBranchesProvider);
    final business = isBusinessCustomer(_type);

    return Scaffold(
      appBar: AppBar(title: const Text('Add customer')),
      body: branches.when(
        loading: () => const LpgSkeletonList(itemCount: 5),
        error: (err, _) => LpgErrorState(
          message: 'Could not load the branches.',
          onRetry: () => ref.invalidate(fleetBranchesProvider),
        ),
        data: (list) => Form(
          key: _form,
          autovalidateMode: AutovalidateMode.onUserInteraction,
          child: ListView(
            padding: LpgSpacing.page,
            children: [
              LpgDropdownField<String>(
                label: 'Customer type',
                prefixIcon: LpgIcons.customers,
                value: _type,
                items: customerTypeLabels,
                onChanged: _busy
                    ? null
                    : (v) {
                        if (v != null) setState(() => _type = v);
                      },
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: business ? 'Business name' : 'Full name',
                isRequired: true,
                controller: _name,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
                validator: (v) => _required(
                  v,
                  business ? 'Enter the business name.' : 'Enter the name.',
                ),
              ),
              if (business) ...[
                const SizedBox(height: LpgSpacing.lg),
                LpgTextField(
                  label: 'Contact person',
                  isRequired: _type == 'commercial',
                  controller: _contact,
                  textCapitalization: TextCapitalization.words,
                  textInputAction: TextInputAction.next,
                  enabled: !_busy,
                  validator: (v) => _type == 'commercial'
                      ? _required(v, 'Enter who to contact at the business.')
                      : null,
                ),
              ],
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'Mobile number',
                isRequired: true,
                prefixIcon: LpgIcons.phone,
                controller: _phone,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
                validator: (v) => normalizeMobile(v ?? '') == null
                    ? 'Enter a 10-digit mobile number.'
                    : null,
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'Another number (optional)',
                prefixIcon: LpgIcons.phone,
                controller: _altPhone,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
                validator: (v) =>
                    (v ?? '').trim().isEmpty || normalizeMobile(v!) != null
                    ? null
                    : 'Enter a 10-digit mobile number.',
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'Email (optional)',
                prefixIcon: LpgIcons.email,
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
                validator: (v) => (v ?? '').trim().isEmpty || isValidEmail(v!)
                    ? null
                    : 'Enter a valid email.',
              ),
              if (business) ...[
                const SizedBox(height: LpgSpacing.lg),
                LpgTextField(
                  label: 'GSTIN (optional)',
                  helperText: 'Printed on their tax invoices.',
                  controller: _gstin,
                  textCapitalization: TextCapitalization.characters,
                  textInputAction: TextInputAction.next,
                  inputFormatters: [LengthLimitingTextInputFormatter(15)],
                  enabled: !_busy,
                  validator: (v) => (v ?? '').trim().isEmpty || isValidGstin(v!)
                      ? null
                      : 'Enter the 15-character GSTIN.',
                ),
              ],
              if (list.length > 1) ...[
                const SizedBox(height: LpgSpacing.lg),
                LpgDropdownField<String>(
                  label: 'Branch',
                  isRequired: true,
                  prefixIcon: LpgIcons.agency,
                  placeholder: 'Choose the branch',
                  value: _branchId ?? '',
                  items: {for (final b in list) b.id: b.name},
                  onChanged: _busy
                      ? null
                      : (v) => setState(() => _branchId = v),
                ),
              ],
              const SizedBox(height: LpgSpacing.xl),
              Text('Delivery address', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                label: 'House, building and street',
                isRequired: true,
                controller: _line1,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
                validator: (v) => _required(v, 'Enter the address.'),
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'Area (optional)',
                controller: _area,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'Landmark (optional)',
                helperText: 'Helps the driver find the place.',
                controller: _landmark,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'City',
                isRequired: true,
                controller: _city,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                enabled: !_busy,
                validator: (v) => _required(v, 'Enter the city.'),
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgDropdownField<String>(
                label: 'State (optional)',
                prefixIcon: LpgIcons.map,
                placeholder: 'Choose the state',
                value: _state ?? '',
                items: {for (final s in indianStates) s: s},
                onChanged: _busy ? null : (v) => setState(() => _state = v),
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'PIN code',
                isRequired: true,
                controller: _pincode,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(6),
                ],
                enabled: !_busy,
                validator: (v) => isValidPincode(v ?? '')
                    ? null
                    : 'Enter the 6-digit PIN code.',
              ),
              if (_error != null) ...[
                const SizedBox(height: LpgSpacing.lg),
                LpgBanner(tone: LpgTone.danger, message: _error!),
              ],
              const SizedBox(height: LpgSpacing.lg),
              Text(
                'They can book as soon as they are added. Approve them later to give them a consumer number.',
                style: text.bodySmall?.copyWith(color: colors.textSecondary),
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgButton(
                label: 'Add customer',
                icon: LpgIcons.add,
                isLoading: _busy,
                expand: true,
                onPressed: _busy ? null : () => _submit(list),
              ),
              const SizedBox(height: LpgSpacing.xl),
            ],
          ),
        ),
      ),
    );
  }
}
