import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../data/profile_provider.dart';

/// Same rule as the server: digits, spaces and dashes, an optional leading
/// plus, 7 to 20 characters. It is a number people read, not a sign-in id.
final _contactPhone = RegExp(r'^\+?[0-9][0-9 \-]{5,18}[0-9]$');

/// Why a name or phone cannot be saved, or `null` when both are fine. Both
/// may be blank: a blank name falls back to the email, a blank phone clears it.
@visibleForTesting
String? profileProblem({required String name, required String phone}) {
  if (name.trim().length > 120) {
    return 'The name can be at most 120 characters.';
  }
  final p = phone.trim();
  if (p.isNotEmpty && !_contactPhone.hasMatch(p)) {
    return 'Enter a phone number with digits, spaces, + or - only.';
  }
  return null;
}

/// Edit the signed-in admin's own name and contact number. Pops `true` once
/// saved.
class EditProfileSheet extends ConsumerStatefulWidget {
  const EditProfileSheet({super.key, required this.profile});

  final AdminProfile profile;

  @override
  ConsumerState<EditProfileSheet> createState() => _EditProfileSheetState();
}

class _EditProfileSheetState extends ConsumerState<EditProfileSheet> {
  late final _name = TextEditingController(text: widget.profile.ownName ?? '');
  late final _phone = TextEditingController(
    text: widget.profile.contactPhone ?? '',
  );
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final problem = profileProblem(name: _name.text, phone: _phone.text);
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(authApiProvider)
        .updateMyProfile(
          displayName: _name.text.trim(),
          contactPhone: _phone.text.trim(),
        );
    if (!mounted) return;
    switch (result) {
      case Success<MyProfile>():
        ref.invalidate(adminProfileProvider);
        Navigator.of(context).pop(true);
      case FailureResult<MyProfile>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return LpgSheetLayout(
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Your name appears across the app. Your sign-in email '
            '(${widget.profile.email ?? 'not set'}) cannot be changed here.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Name',
            controller: _name,
            prefixIcon: LpgIcons.profile,
            maxLength: 120,
            textCapitalization: TextCapitalization.words,
            enabled: !_busy,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Contact phone',
            controller: _phone,
            prefixIcon: LpgIcons.phone,
            keyboardType: TextInputType.phone,
            helperText: 'For colleagues to reach you. Optional.',
            enabled: !_busy,
          ),
        ],
      ),
      footer: LpgSheetActions(
        primaryLabel: 'Save changes',
        primaryIcon: LpgIcons.check,
        isLoading: _busy,
        onPrimary: _busy ? null : _save,
        error: _error,
      ),
    );
  }
}
