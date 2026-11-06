import 'package:flutter/material.dart';

import '../i18n/lpg_strings_delegate.dart';
import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import '../theme_mode.dart';
import 'lpg_card.dart';
import 'lpg_choice_chips.dart';

/// "Appearance": follow the phone, or always light, or always dark. Shared by
/// the profile screens of all three apps, so the choice looks and behaves the
/// same everywhere. Applies at once.
class LpgThemeModePicker extends StatelessWidget {
  const LpgThemeModePicker({super.key, required this.controller});

  final LpgThemeModeController controller;

  @override
  Widget build(BuildContext context) {
    final strings = context.lpgStrings.appearance;
    final text = context.lpgText;
    final colors = context.lpgColors;

    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(strings.title, style: text.titleSmall),
          const SizedBox(height: LpgSpacing.xs),
          Text(
            strings.hint,
            style: text.bodySmall?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.smd),
          ValueListenableBuilder<ThemeMode>(
            valueListenable: controller,
            builder: (context, mode, _) => LpgChoiceChips<ThemeMode>(
              selected: mode,
              onSelected: (picked) {
                if (picked != null) controller.select(picked);
              },
              options: {
                ThemeMode.system: strings.system,
                ThemeMode.light: strings.light,
                ThemeMode.dark: strings.dark,
              },
              icons: const {
                ThemeMode.system: LpgIcons.smartphone,
                ThemeMode.light: LpgIcons.sun,
                ThemeMode.dark: LpgIcons.moon,
              },
            ),
          ),
        ],
      ),
    );
  }
}
