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

/// Adds a van: registration, make and model, ownership, how many cylinders it
/// holds, and the registration certificate (RC) photo with its expiry.
class VehicleFormScreen extends ConsumerStatefulWidget {
  const VehicleFormScreen({super.key});

  @override
  ConsumerState<VehicleFormScreen> createState() => _VehicleFormScreenState();
}

class _VehicleFormScreenState extends ConsumerState<VehicleFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _registration = TextEditingController();
  final _make = TextEditingController();
  final _model = TextEditingController();
  final _capacity = TextEditingController(text: '20');

  String? _branchId;
  var _ownership = 'owned';
  DateTime? _rcExpiry;
  String? _blobRef;
  var _submitted = false;
  var _busy = false;
  String? _error;

  @override
  void dispose() {
    _registration.dispose();
    _make.dispose();
    _model.dispose();
    _capacity.dispose();
    super.dispose();
  }

  void _onRecognized(RecognizedComplianceDocument doc) {
    setState(() {
      if (doc.registrationNumber != null && _registration.text.trim().isEmpty) {
        _registration.text = normalizeRegistration(doc.registrationNumber!);
      }
      if (doc.makerModel != null && _make.text.trim().isEmpty) {
        _make.text = doc.makerModel!;
      }
      _rcExpiry ??= doc.validTill ?? doc.insuranceUpto;
    });
  }

  Future<void> _submit(List<FleetBranch> branches) async {
    setState(() => _submitted = true);
    final branchId =
        _branchId ?? (branches.length == 1 ? branches[0].id : null);
    if (!_formKey.currentState!.validate() ||
        branchId == null ||
        _rcExpiry == null ||
        _blobRef == null) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(fleetApiProvider)
        .registerVehicle(
          branchId: branchId,
          registrationNumber: normalizeRegistration(_registration.text),
          make: _make.text.trim(),
          model: _model.text.trim(),
          ownershipType: _ownership,
          capacityUnits: int.parse(_capacity.text.trim()),
          rcDocumentRef: _blobRef!,
          rcExpiryDate: _rcExpiry!,
        );
    if (!mounted) return;
    switch (result) {
      case FailureResult<FleetVehicle>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
      case Success<FleetVehicle>(:final value):
        refreshFleet(ref);
        context.pop();
        LpgFeedback.showToast(
          context,
          '${value.registrationNumber} added.',
          tone: LpgTone.success,
        );
    }
  }

  String? Function(String?) _required(String message) =>
      (v) => v == null || v.trim().isEmpty ? message : null;

  @override
  Widget build(BuildContext context) {
    final branchesAsync = ref.watch(fleetBranchesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Add van')),
      body: branchesAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgErrorState(
          message: errorMessage(err),
          onRetry: () => ref.invalidate(fleetBranchesProvider),
        ),
        data: (branches) {
          final branchId =
              _branchId ?? (branches.length == 1 ? branches[0].id : null);
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
                        : (id) => setState(() => _branchId = id),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  DocumentPhotoField(
                    label: 'Registration certificate (RC) photo',
                    docKind: 'vehicle_rc',
                    onUploaded: (ref) => setState(() => _blobRef = ref),
                    onRecognized: _onRecognized,
                    errorText: _submitted && _blobRef == null
                        ? 'Add a photo of the registration certificate.'
                        : null,
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgTextField(
                    label: 'Registration number',
                    isRequired: true,
                    prefixIcon: LpgIcons.number,
                    controller: _registration,
                    textCapitalization: TextCapitalization.characters,
                    textInputAction: TextInputAction.next,
                    maxLength: 20,
                    validator: _required('Enter the registration number.'),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgDateField(
                    label: 'RC expiry',
                    isRequired: true,
                    value: _rcExpiry,
                    errorText: _submitted && _rcExpiry == null
                        ? 'Enter the RC expiry date.'
                        : null,
                    onChanged: (d) => setState(() => _rcExpiry = d),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgTextField(
                    label: 'Make',
                    isRequired: true,
                    controller: _make,
                    textCapitalization: TextCapitalization.words,
                    textInputAction: TextInputAction.next,
                    validator: _required('Enter the make.'),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgTextField(
                    label: 'Model',
                    isRequired: true,
                    controller: _model,
                    textCapitalization: TextCapitalization.words,
                    textInputAction: TextInputAction.next,
                    validator: _required('Enter the model.'),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgDropdownField<String>(
                    label: 'Ownership',
                    value: _ownership,
                    items: ownershipTypes,
                    onChanged: _busy
                        ? null
                        : (v) => setState(() => _ownership = v ?? 'owned'),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgTextField(
                    label: 'Capacity (cylinders)',
                    isRequired: true,
                    helperText: 'How many cylinders the van carries.',
                    controller: _capacity,
                    keyboardType: TextInputType.number,
                    validator: (v) {
                      final n = int.tryParse(v?.trim() ?? '');
                      return n == null || n < 1
                          ? 'Capacity must be at least 1.'
                          : null;
                    },
                  ),
                  const SizedBox(height: LpgSpacing.xl),
                  LpgButton(
                    label: 'Add van',
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
}
