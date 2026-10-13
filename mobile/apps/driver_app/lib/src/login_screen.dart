import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';
import 'dev_otp_provider.dart';

/// OTP sign-in — the Driver App's authentication path (Dashboard staff sign
/// in with a password instead, `frontend/libs/auth/feature-login`).
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

  bool _codeRequested = false;
  String? _devOtp;
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
        .requestOtp(tenantId: tenantId, phoneNumber: phone);

    if (!mounted) return;
    // Testing aid until an SMS/WhatsApp gateway exists — see
    // `dev_otp_provider.dart`. Null (and so no banner) outside dev.
    final requested = result.when(
      onSuccess: (_) => true,
      onFailure: (_) => false,
    );
    final devOtp = requested
        ? await ref.read(devOtpLookupProvider)(phone)
        : null;

    if (!mounted) return;
    setState(() {
      _submitting = false;
      _devOtp = devOtp;
      result.when(
        onSuccess: (_) => _codeRequested = true,
        onFailure: (failure) => _errorMessage = failure.message,
      );
    });
  }

  /// Backs out of the "code requested" state so a driver isn't stuck
  /// re-submitting a code that can never work (typo'd number, expired code).
  void _editDetails() {
    setState(() {
      _codeRequested = false;
      _devOtp = null;
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
                      if (_devOtp != null) ...[
                        _DevOtpBanner(code: _devOtp!),
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

/// Shows the one-time code on screen while no SMS provider exists. Rendered
/// only when the dev OTP lookup returned a code, so it disappears on its own
/// once real delivery replaces it.
class _DevOtpBanner extends StatelessWidget {
  const _DevOtpBanner({required this.code});

  final String code;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.actionPrimary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colors.actionPrimary.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(
            'Testing only: your code is',
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          SelectableText(
            code,
            key: const Key('dev-otp-code'),
            style: theme.textTheme.headlineSmall?.copyWith(
              color: colors.textPrimary,
              fontWeight: FontWeight.w800,
              letterSpacing: 4,
            ),
          ),
        ],
      ),
    );
  }
}
