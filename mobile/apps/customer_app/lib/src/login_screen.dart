import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';

/// OTP sign-in — the Customer App's authentication path (Dashboard staff
/// sign in with a password instead, `frontend/libs/auth/feature-login`).
///
/// `tenantId` is a plain text field for now: real tenant resolution
/// (subdomain, build flavor, or a bootstrap screen) is a client-
/// bootstrapping concern the backend's own `RequestOtpUseCase` docstring
/// explicitly defers past this phase. A successful verify updates
/// `authControllerProvider`'s state; `router.dart`'s `redirect:` reacts to
/// that via `refreshListenable` — this screen never navigates explicitly.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _tenantIdController = TextEditingController();
  final _phoneController = TextEditingController();
  final _codeController = TextEditingController();

  bool _codeRequested = false;
  bool _submitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _tenantIdController.dispose();
    _phoneController.dispose();
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _requestCode() async {
    if (_tenantIdController.text.isEmpty || _phoneController.text.isEmpty) {
      return;
    }
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final result = await ref
        .read(authControllerProvider)
        .requestOtp(
          tenantId: _tenantIdController.text.trim(),
          phoneNumber: _phoneController.text.trim(),
        );

    if (!mounted) return;
    setState(() {
      _submitting = false;
      result.when(
        onSuccess: (_) => _codeRequested = true,
        onFailure: (failure) => _errorMessage = failure.message,
      );
    });
  }

  Future<void> _verifyCode() async {
    if (_codeController.text.isEmpty) return;
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final result = await ref
        .read(authControllerProvider)
        .verifyOtp(
          tenantId: _tenantIdController.text.trim(),
          phoneNumber: _phoneController.text.trim(),
          code: _codeController.text.trim(),
        );

    if (!mounted) return;
    setState(() {
      _submitting = false;
      result.when(
        onSuccess: (_) => null,
        onFailure: (failure) => _errorMessage = failure.message,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;

    return Scaffold(
      appBar: AppBar(title: const Text('Sign in')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_errorMessage != null) ...[
              Text(
                _errorMessage!,
                style: TextStyle(color: colors.statusDanger),
              ),
              const SizedBox(height: 12),
            ],
            TextField(
              controller: _tenantIdController,
              enabled: !_codeRequested,
              decoration: const InputDecoration(labelText: 'Tenant ID'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _phoneController,
              enabled: !_codeRequested,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Phone number'),
            ),
            if (_codeRequested) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _codeController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Verification code',
                ),
              ),
            ],
            const SizedBox(height: 20),
            FilledButton(
              onPressed: _submitting
                  ? null
                  : (_codeRequested ? _verifyCode : _requestCode),
              child: Text(
                _submitting
                    ? 'Please wait…'
                    : (_codeRequested ? 'Verify code' : 'Send code'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
