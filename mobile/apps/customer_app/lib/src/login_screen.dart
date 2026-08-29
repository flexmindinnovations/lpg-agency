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
    debugPrint('LoginScreen: _requestCode called');
    final tenantId = _tenantIdController.text.trim();
    final phone = _phoneController.text.trim();

    if (tenantId.isEmpty || phone.isEmpty) {
      setState(
        () => _errorMessage = 'Please enter both Agency Code and Phone number.',
      );
      return;
    }

    // No format check on the Agency Code beyond non-empty: `tenant.slug`
    // has no format constraint server-side (just a uniqueness one,
    // `uq_tenant_slug`) -- it's whatever human-readable string the tenant
    // was created with (e.g. `dev-tenant`), not a fixed pattern. An
    // earlier version of this screen validated against an invented
    // `AB123456`-style regex that no real tenant's slug would ever match.
    if (!RegExp(r'^\+?[0-9]{10,15}$').hasMatch(phone)) {
      setState(() => _errorMessage = 'Please enter a valid phone number.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    debugPrint('LoginScreen: Requesting OTP for $phone in tenant $tenantId');

    final result = await ref
        .read(authControllerProvider)
        .requestOtp(tenantId: tenantId, phoneNumber: phone);

    if (!mounted) return;
    setState(() {
      _submitting = false;
      result.when(
        onSuccess: (_) {
          debugPrint('LoginScreen: OTP requested successfully');
          _codeRequested = true;
        },
        onFailure: (failure) {
          debugPrint('LoginScreen: OTP request failed: ${failure.message}');
          _errorMessage = failure.message;
        },
      );
    });
  }

  /// Backs out of the "code requested" state — re-enables Agency Code /
  /// Phone number and drops the (possibly now-expired, or simply wrong)
  /// code, so a customer isn't stuck re-submitting a code that can never
  /// work with no way to fix a typo'd number or request a fresh one.
  void _editDetails() {
    setState(() {
      _codeRequested = false;
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

    debugPrint(
      'LoginScreen: Verifying OTP for ${_phoneController.text.trim()}',
    );

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
        onSuccess: (_) => debugPrint('LoginScreen: OTP verified successfully'),
        onFailure: (failure) {
          debugPrint(
            'LoginScreen: OTP verification failed: ${failure.message}',
          );
          _errorMessage = failure.message;
        },
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
                      enabled: !_codeRequested,
                    ),
                    const SizedBox(height: 24),
                    LpgTextField(
                      label: 'Phone number',
                      controller: _phoneController,
                      enabled: !_codeRequested,
                      keyboardType: TextInputType.phone,
                    ),
                    if (_codeRequested) ...[
                      const SizedBox(height: 24),
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
                      label: _codeRequested ? 'Verify Code' : 'Send Code',
                      isLoading: _submitting,
                      expand: true,
                      onPressed: _codeRequested ? _verifyCode : _requestCode,
                    ),
                  ],
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
