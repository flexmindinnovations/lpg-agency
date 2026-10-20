import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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

  /// The number the code was sent to, in E.164 — what verify must send.
  String? _requestedPhone;
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
    final rawPhone = _phoneController.text.trim();

    if (tenantId.isEmpty || rawPhone.isEmpty) {
      setState(
        () => _errorMessage = 'Please enter both Agency Code and Phone number.',
      );
      return;
    }
    // No format check on the Agency Code beyond non-empty — `tenant.slug` has
    // no server-side format constraint, just uniqueness.
    // The backend matches accounts on E.164 (`+919876543210`); people type
    // ten digits, or add 0 / 91 / spaces. Normalise here (CA-02).
    final phone = PhoneNumbers.normalize(rawPhone);
    if (phone == null) {
      setState(
        () => _errorMessage =
            'Enter your 10-digit mobile number, for example 98765 43210.',
      );
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
        onSuccess: (_) {
          _codeRequested = true;
          _requestedPhone = phone;
        },
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
          phoneNumber: _requestedPhone!,
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
                  child: Center(
                    child: LpgBrandMark(
                      image: AssetImage('assets/images/lpg_app_logo.jpg'),
                    ),
                  ),
                ),
                const SizedBox(height: LpgSpacing.lg),
                LpgFadeSlideIn(
                  index: 1,
                  child: Column(
                    children: [
                      Semantics(
                        header: true,
                        child: Text(
                          'Driver Sign In',
                          style: text.headlineMedium,
                          textAlign: TextAlign.center,
                        ),
                      ),
                      const SizedBox(height: LpgSpacing.sm),
                      Text(
                        _codeRequested
                            ? 'Enter the code we sent to $_requestedPhone'
                            : 'Sign in to your delivery account',
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
                          label: 'Mobile number',
                          prefixIcon: LpgIcons.phone,
                          // India's code is shown, so a 10-digit number is
                          // all anyone needs to type (CA-02).
                          prefixText: '${PhoneNumbers.indiaDialCode} ',
                          hintText: '10-digit mobile number',
                          controller: _phoneController,
                          enabled: !_codeRequested,
                          keyboardType: TextInputType.phone,
                          inputFormatters: [
                            FilteringTextInputFormatter.allow(
                              RegExp(r'[0-9+\s\-]'),
                            ),
                          ],
                          autofillHints: const [AutofillHints.telephoneNumber],
                          textInputAction: TextInputAction.done,
                          onSubmitted: (_) => _requestCode(),
                        ),
                        if (_codeRequested) ...[
                          const SizedBox(height: LpgSpacing.mdl),
                          if (_devOtp case final devOtp?) ...[
                            LpgDevOtpBanner(code: devOtp),
                            const SizedBox(height: LpgSpacing.md),
                          ],
                          LpgTextField(
                            label: 'Verification code',
                            prefixIcon: LpgIcons.lock,
                            controller: _codeController,
                            keyboardType: TextInputType.number,
                            autofillHints: const [AutofillHints.oneTimeCode],
                            autofocus: true,
                            textInputAction: TextInputAction.done,
                            onSubmitted: (_) => _verifyCode(),
                          ),
                          const SizedBox(height: LpgSpacing.sm),
                          Align(
                            alignment: Alignment.centerRight,
                            child: LpgButton(
                              label: 'Edit Agency Code / Phone Number',
                              icon: LpgIcons.edit,
                              variant: LpgButtonVariant.text,
                              onPressed: _submitting ? null : _editDetails,
                            ),
                          ),
                        ],
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
