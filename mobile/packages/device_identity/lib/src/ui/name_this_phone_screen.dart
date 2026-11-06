import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

import '../device_strings.dart';

/// Asks the user to name the phone, once, before their first sign-in. The name
/// is what the agency sees in its list ("Ravi's Redmi"), so a driver can be
/// told apart from the next one. Also says why the agency is told about the
/// phone at all.
class NameThisPhoneScreen extends StatefulWidget {
  const NameThisPhoneScreen({
    super.key,
    required this.strings,
    required this.suggestedName,
    required this.onSubmit,
  });

  final DeviceStrings strings;

  /// What the field starts with (the phone's model).
  final String suggestedName;

  /// Called with the trimmed name when the user continues.
  final Future<void> Function(String name) onSubmit;

  @override
  State<NameThisPhoneScreen> createState() => _NameThisPhoneScreenState();
}

class _NameThisPhoneScreenState extends State<NameThisPhoneScreen> {
  late final TextEditingController _controller;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.suggestedName);
    _controller.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _canContinue => _controller.text.trim().isNotEmpty && !_saving;

  Future<void> _submit() async {
    if (!_canContinue) return;
    setState(() => _saving = true);
    try {
      await widget.onSubmit(_controller.text.trim());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final strings = widget.strings;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: LpgSpacing.page,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: LpgSpacing.xl),
              Semantics(
                header: true,
                child: Text(strings.nameTitle, style: text.headlineSmall),
              ),
              const SizedBox(height: LpgSpacing.sm),
              Text(
                strings.nameIntro,
                style: text.bodyLarge?.copyWith(color: colors.textSecondary),
              ),
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: strings.nameFieldLabel,
                hintText: strings.nameFieldHint,
                controller: _controller,
                textInputAction: TextInputAction.done,
                textCapitalization: TextCapitalization.words,
                maxLength: 60,
                autofocus: true,
                onSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgBanner(message: strings.nameWhy, icon: LpgIcons.security),
              const SizedBox(height: LpgSpacing.lg),
              LpgButton(
                label: strings.nameContinue,
                expand: true,
                isLoading: _saving,
                onPressed: _canContinue ? _submit : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
