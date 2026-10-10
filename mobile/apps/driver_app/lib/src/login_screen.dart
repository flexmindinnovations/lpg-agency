import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';

/// Two-step sign-in — the Driver App's authentication path: email + password
/// first, then a one-time code (Dashboard staff sign in with a password
/// alone, `frontend/libs/auth/feature-login`).
///
/// Step 1 calls `POST /auth/driver-login`, which checks the password and
/// issues the OTP. There is no SMS provider yet, so while the backend runs
/// with `otp_delivery_dev_mode` it returns the code ([DriverLoginChallenge.
/// devOtp]) and this screen shows it in a banner for the driver to type in;
/// in any other deployment `devOtp` is null and the banner is not shown, so
/// no client change is needed when SMS delivery lands. A successful verify
/// updates `authControllerProvider`'s state; `router.dart`'s `redirect:`
/// reacts to that via `refreshListenable` — this screen never navigates
/// explicitly.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _codeController = TextEditingController();

  DriverLoginChallenge? _challenge;
  bool _submitting = false;
  String? _errorMessage;

  bool get _codeRequested => _challenge != null;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _submitPassword() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text;

    if (email.isEmpty || password.isEmpty) {
      setState(() => _errorMessage = 'Please enter both Email and Password.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final result = await ref
        .read(authControllerProvider)
        .startDriverLogin(email: email, password: password);

    if (!mounted) return;
    setState(() {
      _submitting = false;
      result.when(
        onSuccess: (challenge) => _challenge = challenge,
        onFailure: (failure) => _errorMessage = failure.message,
      );
    });
  }

  /// Backs out of the "code issued" state so a driver isn't stuck
  /// re-submitting a code that can never work (typo'd password, expired code).
  void _editDetails() {
    setState(() {
      _challenge = null;
      _codeController.clear();
      _passwordController.clear();
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
        .verifyDriverLogin(
          email: _emailController.text.trim(),
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
                      label: 'Email',
                      controller: _emailController,
                      enabled: !_codeRequested,
                      keyboardType: TextInputType.emailAddress,
                    ),
                    const SizedBox(height: 24),
                    LpgTextField(
                      label: 'Password',
                      controller: _passwordController,
                      enabled: !_codeRequested,
                      obscureText: true,
                    ),
                    if (_codeRequested) ...[
                      const SizedBox(height: 24),
                      if (_challenge!.devOtp != null) ...[
                        _DevOtpBanner(code: _challenge!.devOtp!),
                        const SizedBox(height: 16),
                      ],
                      LpgTextField(
                        label: 'Verification code',
                        controller: _codeController,
                        helperText: 'Code sent to ${_challenge!.phoneHint}',
                        keyboardType: TextInputType.number,
                        autofocus: true,
                      ),
                      const SizedBox(height: 12),
                      Align(
                        alignment: Alignment.centerRight,
                        child: LpgButton(
                          label: 'Change email / password',
                          variant: LpgButtonVariant.text,
                          onPressed: _submitting ? null : _editDetails,
                        ),
                      ),
                    ],
                    const SizedBox(height: 28),
                    LpgButton(
                      label: _codeRequested ? 'Verify Code' : 'Continue',
                      isLoading: _submitting,
                      expand: true,
                      onPressed: _codeRequested ? _verifyCode : _submitPassword,
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
/// only when the backend returned a `devOtp` (development builds of the
/// backend), so it disappears on its own once real delivery replaces it.
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
            'Development mode: your code is',
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
