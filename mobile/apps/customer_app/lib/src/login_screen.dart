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
    final tenantId = _tenantIdController.text.trim();
    final phone = _phoneController.text.trim();

    if (tenantId.isEmpty || phone.isEmpty) {
      setState(() => _errorMessage = 'Please enter both Agency Code and Phone number.');
      return;
    }

    if (!RegExp(r'^[A-Za-z]{2}\d{4,6}$').hasMatch(tenantId)) {
      setState(() => _errorMessage = 'Invalid Agency Code format (e.g. AB123456).');
      return;
    }

    if (!RegExp(r'^\+?[0-9]{10,15}$').hasMatch(phone)) {
      setState(() => _errorMessage = 'Please enter a valid phone number.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final result = await ref
        .read(authControllerProvider)
        .requestOtp(
          tenantId: tenantId,
          phoneNumber: phone,
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
    if (_codeController.text.trim().isEmpty) {
      setState(() => _errorMessage = 'Please enter the verification code.');
      return;
    }
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
    final theme = Theme.of(context);

    final inputDecoration = InputDecoration(
      filled: true,
      fillColor: colors.surfaceRaised,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: colors.borderDefault),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: colors.actionPrimary, width: 2),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      labelStyle: theme.textTheme.bodyMedium?.copyWith(
        color: colors.textSecondary,
      ),
    );

    return Scaffold(
      backgroundColor: colors.surfaceBase,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 48),
              Center(
                child: Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: colors.actionPrimary.withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.local_fire_department_rounded,
                    size: 32,
                    color: colors.actionPrimary,
                  ),
                ),
              ),
              const SizedBox(height: 32),
              Text(
                'Welcome',
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: colors.textPrimary,
                  letterSpacing: -0.5,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Sign in to your account',
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: colors.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 48),
              
              if (_errorMessage != null) ...[
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colors.statusDanger.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: colors.statusDanger.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: colors.statusDanger),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: TextStyle(color: colors.statusDanger, fontWeight: FontWeight.w500),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
              ],
              
              TextField(
                controller: _tenantIdController,
                enabled: !_codeRequested,
                decoration: inputDecoration.copyWith(labelText: 'Agency Code'),
                style: TextStyle(color: colors.textPrimary),
              ),
              const SizedBox(height: 16),
              
              TextField(
                controller: _phoneController,
                enabled: !_codeRequested,
                keyboardType: TextInputType.phone,
                decoration: inputDecoration.copyWith(labelText: 'Phone number'),
                style: TextStyle(color: colors.textPrimary),
              ),
              
              if (_codeRequested) ...[
                const SizedBox(height: 16),
                TextField(
                  controller: _codeController,
                  keyboardType: TextInputType.number,
                  decoration: inputDecoration.copyWith(labelText: 'Verification code'),
                  style: TextStyle(color: colors.textPrimary),
                  autofocus: true,
                ),
              ],
              
              const SizedBox(height: 32),
              
              SizedBox(
                height: 56,
                child: ElevatedButton(
                  onPressed: _submitting
                      ? null
                      : (_codeRequested ? _verifyCode : _requestCode),
                  child: _submitting
                      ? SizedBox(
                          height: 24,
                          width: 24,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              LpgTokens.primitiveColorWhite,
                            ),
                          ),
                        )
                      : Text(_codeRequested ? 'Verify Code' : 'Send Code'),
                ),
              ),

              const SizedBox(height: 48),

              Text(
                'By signing in, you agree to our',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colors.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 4),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'Terms of Service',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.actionPrimary,
                      fontWeight: FontWeight.bold,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                  Text(
                    ' and ',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  Text(
                    'Privacy Policy',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.actionPrimary,
                      fontWeight: FontWeight.bold,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              Text(
                'v1.0.0 (Build 1)',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colors.textSecondary.withValues(alpha: 0.5),
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
