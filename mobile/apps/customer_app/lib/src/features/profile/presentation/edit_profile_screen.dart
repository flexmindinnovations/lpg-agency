import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

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
    _altMobileController = TextEditingController(text: widget.profile.alternateMobile ?? '');
    _contactPersonController = TextEditingController(text: widget.profile.contactPerson ?? '');
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
      email: _emailController.text.trim().isEmpty ? null : _emailController.text.trim(),
      alternateMobile: _altMobileController.text.trim().isEmpty ? null : _altMobileController.text.trim(),
      contactPerson: _contactPersonController.text.trim().isEmpty ? null : _contactPersonController.text.trim(),
      dateOfBirth: widget.profile.dateOfBirth,
      lpgSubsidyId: widget.profile.lpgSubsidyId,
    );

    final result = await api.updateCustomer(widget.profile.id, request);
    
    if (mounted) {
      setState(() => _isLoading = false);
      result.when(
        onSuccess: (data) {
          ref.invalidate(profileProvider);
          context.pop();
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Profile updated successfully')),
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
          'Edit Profile',
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
                    TextFormField(
                      controller: _fullNameController,
                      decoration: const InputDecoration(labelText: 'Full Name'),
                      validator: (value) => value == null || value.isEmpty ? 'Required' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _phoneController,
                      decoration: const InputDecoration(labelText: 'Phone Number'),
                      validator: (value) => value == null || value.isEmpty ? 'Required' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _emailController,
                      decoration: const InputDecoration(labelText: 'Email Address'),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _altMobileController,
                      decoration: const InputDecoration(labelText: 'Alternate Mobile'),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _contactPersonController,
                      decoration: const InputDecoration(labelText: 'Contact Person'),
                    ),
                    const SizedBox(height: 32),
                    ElevatedButton(
                      onPressed: _save,
                      child: const Text('Save Changes'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
