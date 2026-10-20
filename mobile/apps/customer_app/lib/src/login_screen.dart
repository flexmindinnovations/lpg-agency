import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';
import 'dev_otp_provider.dart';
import 'splash_screen.dart' show appLogo;

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

  /// Testing only: the code read back from the backend's dev inbox so a tester
  /// can sign in without an SMS. Null in production (route absent). Remove with
  /// the SMS/WhatsApp gateway integration.
  String? _testingOtp;
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
    final phone = normalizePhoneNumber(_phoneController.text);

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

    debugPrint('LoginScreen: Requesting OTP for $phone in tenant $tenantId');

    final result = await ref
        .read(authControllerProvider)
        .requestOtp(tenantId: tenantId, phoneNumber: phone);

    // Testing aid until an SMS/WhatsApp gateway exists — see
    // `dev_otp_provider.dart`. Null (and so no banner) outside dev.
    final testingOtp = result is Success
        ? await ref.read(devOtpLookupProvider)(phone)
        : null;
    if (!mounted) return;
    setState(() {
      _submitting = false;
      result.when(
        onSuccess: (_) {
          debugPrint('LoginScreen: OTP requested successfully');
          _codeRequested = true;
          _testingOtp = testingOtp;
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
      _testingOtp = null;
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
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            LpgSpacing.lg,
            LpgSpacing.xxl,
            LpgSpacing.lg,
            LpgSpacing.lg,
          ),
          child: AutofillGroup(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const LpgFadeSlideIn(
                  child: Center(child: LpgBrandMark(image: appLogo)),
                ),
                const SizedBox(height: LpgSpacing.lg),
                LpgFadeSlideIn(
                  index: 1,
                  child: Column(
                    children: [
                      Semantics(
                        header: true,
                        child: Text(
                          'Welcome',
                          style: text.headlineMedium,
                          textAlign: TextAlign.center,
                        ),
                      ),
                      const SizedBox(height: LpgSpacing.sm),
                      Text(
                        _codeRequested
                            ? 'Enter the code we sent to ${_phoneController.text.trim()}'
                            : 'Sign in with your phone number',
                        style: text.bodyLarge?.copyWith(
                          color: colors.textSecondary,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: LpgSpacing.xl),
                if (_errorMessage != null) ...[
                  LpgBanner(tone: LpgTone.danger, message: _errorMessage!),
                  const SizedBox(height: LpgSpacing.md),
                ],
                LpgFadeSlideIn(
                  index: 2,
                  child: LpgCard(
                    padding: const EdgeInsets.all(LpgSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        LpgTextField(
                          label: 'Agency code',
                          prefixIcon: LpgIcons.agency,
                          controller: _tenantIdController,
                          enabled: !_codeRequested,
                          textInputAction: TextInputAction.next,
                        ),
                        const SizedBox(height: LpgSpacing.mdl),
                        LpgTextField(
                          label: 'Phone number',
                          hintText: '10-digit mobile number',
                          prefixIcon: LpgIcons.phone,
                          controller: _phoneController,
                          enabled: !_codeRequested,
                          keyboardType: TextInputType.phone,
                          autofillHints: const [AutofillHints.telephoneNumber],
                          textInputAction: TextInputAction.done,
                          onSubmitted: (_) => _requestCode(),
                        ),
                        AnimatedSize(
                          duration: LpgMotion.medium(context),
                          curve: Curves.easeOutCubic,
                          alignment: Alignment.topCenter,
                          child: _codeRequested
                              ? Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    const SizedBox(height: LpgSpacing.mdl),
                                    if (_testingOtp case final testingOtp?) ...[
                                      LpgDevOtpBanner(code: testingOtp),
                                      const SizedBox(height: LpgSpacing.md),
                                    ],
                                    LpgTextField(
                                      label: 'Verification code',
                                      prefixIcon: LpgIcons.lock,
                                      controller: _codeController,
                                      keyboardType: TextInputType.number,
                                      autofillHints: const [
                                        AutofillHints.oneTimeCode,
                                      ],
                                      autofocus: true,
                                      textInputAction: TextInputAction.done,
                                      onSubmitted: (_) => _verifyCode(),
                                    ),
                                    const SizedBox(height: LpgSpacing.sm),
                                    Align(
                                      alignment: Alignment.centerRight,
                                      child: LpgButton(
                                        label:
                                            'Edit Agency Code / Phone Number',
                                        icon: LpgIcons.edit,
                                        variant: LpgButtonVariant.text,
                                        onPressed: _submitting
                                            ? null
                                            : _editDetails,
                                      ),
                                    ),
                                  ],
                                )
                              : const SizedBox(width: double.infinity),
                        ),
                        const SizedBox(height: LpgSpacing.lg),
                        LpgButton(
                          label: _codeRequested ? 'Verify Code' : 'Send Code',
                          trailingIcon: _codeRequested
                              ? LpgIcons.check
                              : LpgIcons.chevronRight,
                          isLoading: _submitting,
                          expand: true,
                          onPressed: _codeRequested
                              ? _verifyCode
                              : _requestCode,
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: LpgSpacing.xl),
                Text(
                  'By signing in, you agree to our Terms of Service and '
                  'Privacy Policy.',
                  style: text.bodySmall?.copyWith(color: colors.textSecondary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: LpgSpacing.md),
                Text(
                  'v1.0.0 (Build 1)',
                  style: text.labelSmall?.copyWith(color: colors.textDisabled),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
