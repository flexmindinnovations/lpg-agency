import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';
import 'dev_otp_provider.dart';
import 'splash_screen.dart' show appLogo;

enum _AuthMethod { phoneOtp, emailPassword }

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  _AuthMethod _authMethod = _AuthMethod.phoneOtp;

  // Phone OTP controllers
  final _tenantIdController = TextEditingController();
  final _phoneController = TextEditingController();
  final _codeController = TextEditingController();

  // Email & Password controllers
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;
  bool _codeRequested = false;
  String? _testingOtp;
  bool _submitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _tenantIdController.dispose();
    _phoneController.dispose();
    _codeController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _requestCode() async {
    final tenantId = _tenantIdController.text.trim();
    final phone = normalizePhoneNumber(_phoneController.text);

    if (tenantId.isEmpty || phone.isEmpty) {
      setState(
        () => _errorMessage = 'Please enter both Agency Code and Phone number.',
      );
      return;
    }

    if (!isValidPhoneNumber(phone)) {
      setState(
        () => _errorMessage = 'Please enter a valid 10-digit mobile number.',
      );
      return;
    }

    _phoneController.text = phone;
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final auth = ref.read(authControllerProvider);
    final result = await auth.requestOtp(
      tenantId: tenantId,
      phoneNumber: phone,
    );
    final testingOtp = result is Success
        ? await ref.read(devOtpLookupProvider)(phone)
        : null;

    if (!mounted) return;

    result.when(
      onSuccess: (_) {
        setState(() {
          _codeRequested = true;
          _testingOtp = testingOtp;
          if (testingOtp != null) {
            _codeController.text = testingOtp;
          }
          _submitting = false;
          _errorMessage = null;
        });
        if (_codeRequested) {
          LpgFeedback.showToast(context, 'Verification code requested');
        }
      },
      onFailure: (failure) {
        setState(() {
          _submitting = false;
          _errorMessage = failure.message;
        });
      },
    );
  }

  Future<void> _verifyCode() async {
    final code = _codeController.text.trim();
    if (code.length < 6) {
      setState(
        () => _errorMessage = 'Please enter a 6-digit verification code.',
      );
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final auth = ref.read(authControllerProvider);
    final result = await auth.verifyOtp(
      tenantId: _tenantIdController.text.trim(),
      phoneNumber: normalizePhoneNumber(_phoneController.text),
      code: code,
    );

    if (!mounted) return;

    result.when(
      onSuccess: (_) {},
      onFailure: (failure) {
        setState(() {
          _submitting = false;
          _errorMessage = failure.message;
        });
      },
    );
  }

  Future<void> _loginWithPassword() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text;

    if (email.isEmpty || password.isEmpty) {
      setState(() => _errorMessage = 'Please enter both email and password.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final auth = ref.read(authControllerProvider);
    final result = await auth.login(email: email, password: password);

    if (!mounted) return;

    result.when(
      onSuccess: (_) {},
      onFailure: (failure) {
        setState(() {
          _submitting = false;
          _errorMessage = failure.message;
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Scaffold(
      backgroundColor: colors.canvas,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: LpgSpacing.page,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: LpgSpacing.xl),
              const Center(child: LpgBrandMark(image: appLogo, size: 88)),
              const SizedBox(height: LpgSpacing.lg),
              Text(
                'Admin Console',
                style: text.headlineSmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: LpgSpacing.xs),
              Text(
                'Sign in to manage agency operations',
                style: text.bodyMedium?.copyWith(color: colors.textSecondary),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: LpgSpacing.lg),

              SegmentedButton<_AuthMethod>(
                segments: const [
                  ButtonSegment(
                    value: _AuthMethod.phoneOtp,
                    label: Text('Phone OTP'),
                    icon: Icon(Icons.phone_android),
                  ),
                  ButtonSegment(
                    value: _AuthMethod.emailPassword,
                    label: Text('Email & Password'),
                    icon: Icon(Icons.lock_outline),
                  ),
                ],
                selected: {_authMethod},
                onSelectionChanged: (selected) {
                  setState(() {
                    _authMethod = selected.first;
                    _errorMessage = null;
                  });
                },
              ),

              const SizedBox(height: LpgSpacing.xl),

              if (_errorMessage != null) ...[
                LpgBanner(message: _errorMessage!, tone: LpgTone.danger),
                const SizedBox(height: LpgSpacing.md),
              ],

              if (_authMethod == _AuthMethod.phoneOtp) ...[
                if (_testingOtp != null) ...[
                  LpgDevOtpBanner(code: _testingOtp!),
                  const SizedBox(height: LpgSpacing.md),
                ],
                LpgTextField(
                  controller: _tenantIdController,
                  label: 'Agency Code (Tenant ID)',
                  hintText: 'e.g., dev-tenant',
                  readOnly: _codeRequested || _submitting,
                ),
                const SizedBox(height: LpgSpacing.md),
                LpgTextField(
                  controller: _phoneController,
                  label: 'Mobile Number',
                  hintText: '10-digit phone number',
                  keyboardType: TextInputType.phone,
                  readOnly: _codeRequested || _submitting,
                ),
                if (_codeRequested) ...[
                  const SizedBox(height: LpgSpacing.md),
                  LpgTextField(
                    controller: _codeController,
                    label: '6-digit Verification Code',
                    hintText: 'Enter OTP',
                    keyboardType: TextInputType.number,
                    readOnly: _submitting,
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  LpgButton(
                    label: 'Sign In to Admin',
                    onPressed: _submitting ? null : _verifyCode,
                    isLoading: _submitting,
                  ),
                  const SizedBox(height: LpgSpacing.sm),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      TextButton.icon(
                        onPressed: _submitting ? null : _requestCode,
                        icon: const Icon(LpgIcons.sync, size: LpgSizes.iconSm),
                        label: const Text('Resend / Refresh OTP'),
                      ),
                      TextButton(
                        onPressed: _submitting
                            ? null
                            : () => setState(() => _codeRequested = false),
                        child: const Text('Change Details'),
                      ),
                    ],
                  ),
                ] else ...[
                  const SizedBox(height: LpgSpacing.lg),
                  LpgButton(
                    label: 'Send Sign-In Code',
                    onPressed: _submitting ? null : _requestCode,
                    isLoading: _submitting,
                  ),
                ],
              ] else ...[
                LpgTextField(
                  controller: _emailController,
                  label: 'Email Address',
                  hintText: 'admin@example.com',
                  keyboardType: TextInputType.emailAddress,
                  readOnly: _submitting,
                ),
                const SizedBox(height: LpgSpacing.md),
                LpgTextField(
                  controller: _passwordController,
                  label: 'Password',
                  hintText: 'Enter your password',
                  obscureText: _obscurePassword,
                  readOnly: _submitting,
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscurePassword ? LpgIcons.eyeOff : LpgIcons.eye,
                      size: LpgSizes.iconSm,
                      color: colors.textSecondary,
                    ),
                    onPressed: () =>
                        setState(() => _obscurePassword = !_obscurePassword),
                  ),
                ),
                const SizedBox(height: LpgSpacing.xl),
                LpgButton(
                  label: 'Sign In with Email',
                  onPressed: _submitting ? null : _loginWithPassword,
                  isLoading: _submitting,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
