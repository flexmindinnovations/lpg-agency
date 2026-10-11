import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';

/// Two-step OTP sign-in: Agency Code + phone number first, then the code the
/// backend sends to that phone (Dashboard staff sign in with a password
/// instead, `frontend/libs/auth/feature-login`).
///
/// There is no SMS provider yet (Phase 14), so outside production the
/// backend echoes the code in the step-1 response and this screen shows it
/// for the driver to type — [OtpChallenge.devOtp] is null in production
/// and the banner simply doesn't render. Swap in real delivery by changing
/// only the backend.
///
/// `tenantId` (shown as "Agency Code") is a plain text field for now: real
/// tenant resolution (subdomain, build flavor, or a bootstrap screen) is a
/// client-bootstrapping concern the backend's own `RequestOtpUseCase`
/// docstring explicitly defers. A successful verify updates
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

  /// Non-null once step 1 succeeded: carries the tenant and phone that step 2
  /// (`verifyOtp`) must use, and the dev-only code to display.
  OtpChallenge? _challenge;
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
      setState(
        () => _errorMessage = 'Please enter both Agency Code and Phone number.',
      );
      return;
    }
    // No format check on the Agency Code beyond non-empty — `tenant.slug` has
    // no server-side format constraint, just uniqueness.
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
        .requestDriverOtp(tenantId: tenantId, phoneNumber: phone);

    if (!mounted) return;
    setState(() {
      _submitting = false;
      result.when(
        onSuccess: (challenge) => _challenge = challenge,
        onFailure: (failure) => _errorMessage = failure.message,
      );
    });
  }
  /// Backs out of the "code requested" state so a driver isn't stuck
  /// re-submitting a code that can never work (typo'd number, expired code).
  void _editDetails() {
    setState(() {
      _challenge = null;
      _codeController.clear();
      _errorMessage = null;
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

    final challenge = _challenge!;
    final result = await ref
        .read(authControllerProvider)
        .verifyOtp(
          tenantId: challenge.tenantId,
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
                    Icons.local_shipping_rounded,
                    size: 32,
                    color: colors.actionPrimary,
                  ),
                ),
              ),
              const SizedBox(height: 32),
              Text(
                'Driver Sign In',
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: colors.textPrimary,
                  letterSpacing: -0.5,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Sign in to your delivery account',
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
                    border: Border.all(
                      color: colors.statusDanger.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: colors.statusDanger),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: TextStyle(
                            color: colors.statusDanger,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
              ],

              LpgCard(
                padding: const EdgeInsets.all(32),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    LpgTextField(
                      label: 'Agency Code',
                      controller: _tenantIdController,
                      enabled: _challenge == null,
                    ),
                    const SizedBox(height: 24),
                    LpgTextField(
                      label: 'Phone number',
                      controller: _phoneController,
                      enabled: _challenge == null,
                      keyboardType: TextInputType.phone,
                    ),                    if (_challenge case final challenge?) ...[
                      const SizedBox(height: 24),
                      if (challenge.devOtp case final devOtp?) ...[
                        LpgDevOtpBanner(code: devOtp),
                        const SizedBox(height: 16),
                      ],
                      LpgTextField(
                        label: 'Verification code',
                        controller: _codeController,
                        keyboardType: TextInputType.number,
                        autofocus: true,
                      ),
                      const SizedBox(height: 12),
                      Align(
                        alignment: Alignment.centerRight,
                        child: LpgButton(
                          label: 'Edit Agency Code / Phone Number',
                          variant: LpgButtonVariant.text,
                          onPressed: _submitting ? null : _editDetails,
                        ),
                      ),
                    ],
                    const SizedBox(height: 28),
                    LpgButton(
                      label: _challenge != null ? 'Verify Code' : 'Send Code',
                      isLoading: _submitting,
                      expand: true,
                      onPressed: _challenge != null ? _verifyCode : _requestCode,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 48),
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
