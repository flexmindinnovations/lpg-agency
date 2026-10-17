import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../data/profile_provider.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key, required this.profile});

  final CustomerResponse profile;

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _fullNameController;
  late TextEditingController _phoneController;
  late TextEditingController _emailController;
  late TextEditingController _altMobileController;
  late TextEditingController _contactPersonController;

  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fullNameController = TextEditingController(text: widget.profile.fullName);
    _phoneController = TextEditingController(text: widget.profile.phoneNumber);
    _emailController = TextEditingController(text: widget.profile.email ?? '');
    _altMobileController = TextEditingController(
      text: widget.profile.alternateMobile ?? '',
    );
    _contactPersonController = TextEditingController(
      text: widget.profile.contactPerson ?? '',
    );
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _altMobileController.dispose();
    _contactPersonController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final api = ref.read(customerApiProvider);
    final request = UpdateCustomerProfileRequest(
      branchId: widget.profile.branchId,
      fullName: _fullNameController.text.trim(),
      phoneNumber: _phoneController.text.trim(),
      customerType: widget.profile.customerType,
      status: widget.profile.status,
      email: _emailController.text.trim().isEmpty
          ? null
          : _emailController.text.trim(),
      alternateMobile: _altMobileController.text.trim().isEmpty
          ? null
          : _altMobileController.text.trim(),
      contactPerson: _contactPersonController.text.trim().isEmpty
          ? null
          : _contactPersonController.text.trim(),
      dateOfBirth: widget.profile.dateOfBirth,
      lpgSubsidyId: widget.profile.lpgSubsidyId,
    );

    final result = await api.updateCustomer(widget.profile.id, request);

    if (mounted) {
      setState(() => _isLoading = false);
      result.when(
        onSuccess: (data) {
          final navigator = Navigator.of(context);
          navigator.pop();
          ref.invalidate(profileProvider);
          LpgFeedback.showToast(
            navigator.context,
            'Profile updated successfully',
            tone: LpgTone.success,
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
    const gap = SizedBox(height: LpgSpacing.mdl);
    return Scaffold(
      appBar: AppBar(title: const Text('Edit Profile')),
      body: SingleChildScrollView(
        padding: LpgSpacing.page,
        child: Form(
          key: _formKey,
          child: AutofillGroup(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Center(
                  child: Hero(
                    tag: 'profile_avatar',
                    child: LpgAvatar(
                      name: widget.profile.fullName,
                      size: LpgSizes.avatarLg,
                    ),
                  ),
                ),
                const SizedBox(height: LpgSpacing.lg),
                if (_error != null) ...[
                  LpgBanner(tone: LpgTone.danger, message: _error!),
                  const SizedBox(height: LpgSpacing.lg),
                ],
                LpgTextField(
                  label: 'Full name',
                  isRequired: true,
                  prefixIcon: LpgIcons.user,
                  controller: _fullNameController,
                  textInputAction: TextInputAction.next,
                  textCapitalization: TextCapitalization.words,
                  autofillHints: const [AutofillHints.name],
                  validator: (value) =>
                      value == null || value.isEmpty ? 'Required' : null,
                ),
                gap,
                LpgTextField(
                  label: 'Phone number',
                  isRequired: true,
                  prefixIcon: LpgIcons.phone,
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.telephoneNumber],
                  validator: (value) =>
                      value == null || value.isEmpty ? 'Required' : null,
                ),
                gap,
                LpgTextField(
                  label: 'Email address',
                  prefixIcon: LpgIcons.email,
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.email],
                ),
                gap,
                LpgTextField(
                  label: 'Alternate mobile',
                  prefixIcon: LpgIcons.call,
                  controller: _altMobileController,
                  keyboardType: TextInputType.phone,
                  textInputAction: TextInputAction.next,
                ),
                gap,
                LpgTextField(
                  label: 'Contact person',
                  prefixIcon: LpgIcons.user,
                  controller: _contactPersonController,
                  textInputAction: TextInputAction.done,
                  textCapitalization: TextCapitalization.words,
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
