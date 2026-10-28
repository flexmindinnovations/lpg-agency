import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../data/fleet_providers.dart';
import '../domain/fleet_rules.dart';
import 'document_photo_field.dart';
import 'fleet_screen.dart';

const _newPerson = '';

/// Adds a driver the way the dashboard does: a driver employee (new, or one
/// already on file), the driving licence with its photo, then the Driver App
/// login so they can sign in with their mobile number.
class DriverFormScreen extends ConsumerStatefulWidget {
  const DriverFormScreen({super.key});

  @override
  ConsumerState<DriverFormScreen> createState() => _DriverFormScreenState();
}

class _DriverFormScreenState extends ConsumerState<DriverFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _phone = TextEditingController();
  final _email = TextEditingController();
  final _licence = TextEditingController();

  String? _branchId;
  String _person = _newPerson;
  DateTime? _expiry;
  String? _blobRef;
  var _submitted = false;
  var _busy = false;
  String? _error;

  /// The employee created by an attempt that failed later: a retry reuses
  /// it instead of registering the same person twice.
  FleetEmployee? _createdEmployee;

  @override
  void dispose() {
    _first.dispose();
    _last.dispose();
    _phone.dispose();
    _email.dispose();
    _licence.dispose();
    super.dispose();
  }

  void _onRecognized(RecognizedComplianceDocument doc) {
    setState(() {
      if (doc.documentNumber != null && _licence.text.trim().isEmpty) {
        _licence.text = doc.documentNumber!;
      }
      _expiry ??= doc.validTill;
    });
  }

  Future<void> _submit(List<FleetBranch> branches) async {
    setState(() => _submitted = true);
    final branchId =
        _branchId ?? (branches.length == 1 ? branches[0].id : null);
    if (!_formKey.currentState!.validate() ||
        branchId == null ||
        _expiry == null ||
        _blobRef == null) {
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(fleetApiProvider);

    String employeeId;
    if (_person != _newPerson) {
      employeeId = _person;
    } else if (_createdEmployee != null) {
      employeeId = _createdEmployee!.id;
    } else {
      final created = await api.registerEmployee(
        branchId: branchId,
        firstName: _first.text.trim(),
        lastName: _last.text.trim(),
        phoneNumber: normalizeMobile(_phone.text)!,
        email: _email.text.trim().isEmpty ? null : _email.text.trim(),
      );
      if (!mounted) return;
      switch (created) {
        case FailureResult<FleetEmployee>(:final failure):
          return _fail(failure.message);
        case Success<FleetEmployee>(:final value):
          _createdEmployee = value;
          employeeId = value.id;
      }
    }

    final driver = await api.registerDriver(
      branchId: branchId,
      employeeId: employeeId,
      licenseNumber: _licence.text.trim(),
      licenseExpiryDate: _expiry!,
      licenceDocumentRef: _blobRef!,
    );
    if (!mounted) return;
    if (driver case FailureResult<FleetDriver>(:final failure)) {
      return _fail(failure.message);
    }

    // The login is what lets them into the Driver App. If it fails the
    // driver is still saved and can be enabled from their page.
    final login = await api.enableDriverLogin(employeeId);
    if (!mounted) return;
    refreshFleet(ref);
    final name = driver is Success<FleetDriver> ? driver.value.name : 'Driver';
    final loginFailed = login is FailureResult<void>;
    context.pop();
    LpgFeedback.showToast(
      context,
      loginFailed
          ? '$name added. Enable their Driver App login from their page.'
          : '$name added. They can sign in to the Driver App now.',
      tone: loginFailed ? LpgTone.warning : LpgTone.success,
    );
  }

  void _fail(String message) {
    setState(() {
      _busy = false;
      _error = message;
    });
  }

  @override
  Widget build(BuildContext context) {
    final branchesAsync = ref.watch(fleetBranchesProvider);
    final drivers = ref.watch(fleetDriversProvider).value ?? const [];
    final employees = ref.watch(driverEmployeesProvider).value ?? const [];

    return Scaffold(
      appBar: AppBar(title: const Text('Add driver')),
      body: branchesAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgErrorState(
          message: errorMessage(err),
          onRetry: () => ref.invalidate(fleetBranchesProvider),
        ),
        data: (branches) {
          final branchId =
              _branchId ?? (branches.length == 1 ? branches[0].id : null);
          final taken = {for (final d in drivers) d.employeeId};
          final candidates = [
            for (final e in employees)
              if (e.status == 'active' &&
                  e.branchId == branchId &&
                  !taken.contains(e.id))
                e,
          ];
          final person = candidates.any((e) => e.id == _person)
              ? _person
              : _newPerson;
          final isNew = person == _newPerson;

          return SingleChildScrollView(
            padding: LpgSpacing.page,
            child: Form(
              key: _formKey,
              autovalidateMode: _submitted
                  ? AutovalidateMode.always
                  : AutovalidateMode.disabled,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_error != null) ...[
                    LpgBanner(tone: LpgTone.danger, message: _error!),
                    const SizedBox(height: LpgSpacing.lg),
                  ],
                  LpgDropdownField<String?>(
                    label: 'Branch',
                    isRequired: true,
                    placeholder: 'Choose a branch',
                    prefixIcon: LpgIcons.agency,
                    value: branchId,
                    items: {for (final b in branches) b.id: b.name},
                    validator: (v) => v == null ? 'Select a branch.' : null,
                    onChanged: _busy
                        ? null
                        : (id) => setState(() {
                            _branchId = id;
                            _person = _newPerson;
                          }),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  if (candidates.isNotEmpty) ...[
                    LpgDropdownField<String>(
                      label: 'Person',
                      prefixIcon: LpgIcons.user,
                      value: person,
                      items: {
                        _newPerson: 'New driver',
                        for (final e in candidates)
                          e.id: '${e.fullName} (${e.employeeCode})',
                      },
                      onChanged: _busy
                          ? null
                          : (id) => setState(() => _person = id ?? _newPerson),
                    ),
                    const SizedBox(height: LpgSpacing.lg),
                  ],
                  if (isNew) ...[
                    LpgTextField(
                      label: 'First name',
                      isRequired: true,
                      controller: _first,
                      textCapitalization: TextCapitalization.words,
                      textInputAction: TextInputAction.next,
                      validator: _required('Enter the first name.'),
                    ),
                    const SizedBox(height: LpgSpacing.lg),
                    LpgTextField(
                      label: 'Last name',
                      isRequired: true,
                      controller: _last,
                      textCapitalization: TextCapitalization.words,
                      textInputAction: TextInputAction.next,
                      validator: _required('Enter the last name.'),
                    ),
                    const SizedBox(height: LpgSpacing.lg),
                    LpgTextField(
                      label: 'Mobile number',
                      isRequired: true,
                      helperText: 'They sign in to the Driver App with this.',
                      prefixIcon: LpgIcons.phone,
                      controller: _phone,
                      keyboardType: TextInputType.phone,
                      textInputAction: TextInputAction.next,
                      validator: (v) => normalizeMobile(v ?? '') == null
                          ? 'Enter a 10-digit mobile number.'
                          : null,
                    ),
                    const SizedBox(height: LpgSpacing.lg),
                    LpgTextField(
                      label: 'Email',
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      validator: (v) {
                        final value = v?.trim() ?? '';
                        if (value.isEmpty) return null;
                        return RegExp(
                              r'^[^@\s]+@[^@\s]+\.[^@\s]+$',
                            ).hasMatch(value)
                            ? null
                            : 'Enter a valid email.';
                      },
                    ),
                    const SizedBox(height: LpgSpacing.lg),
                  ],
                  DocumentPhotoField(
                    label: 'Driving licence photo',
                    docKind: 'driving_licence',
                    onUploaded: (ref) => setState(() => _blobRef = ref),
                    onRecognized: _onRecognized,
                    errorText: _submitted && _blobRef == null
                        ? 'Add a photo of the driving licence.'
                        : null,
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgTextField(
                    label: 'Licence number',
                    isRequired: true,
                    prefixIcon: LpgIcons.number,
                    controller: _licence,
                    textCapitalization: TextCapitalization.characters,
                    validator: _required('Enter the licence number.'),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgDateField(
                    label: 'Licence expiry',
                    isRequired: true,
                    value: _expiry,
                    errorText: _submitted && _expiry == null
                        ? 'Enter the licence expiry date.'
                        : null,
                    onChanged: (d) => setState(() => _expiry = d),
                  ),
                  const SizedBox(height: LpgSpacing.xl),
                  LpgButton(
                    label: 'Add driver',
                    icon: LpgIcons.add,
                    expand: true,
                    isLoading: _busy,
                    onPressed: _busy ? null : () => _submit(branches),
                  ),
                  const SizedBox(height: LpgSpacing.xxl),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  String? Function(String?) _required(String message) =>
      (v) => v == null || v.trim().isEmpty ? message : null;
}
