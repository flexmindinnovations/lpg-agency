import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import '../tone.dart';

/// An inline message strip: a form error, an offline notice, a "KYC
/// pending" nudge. Tinted in its [tone], with an optional action.
///
/// Error and warning banners are live regions, so a screen reader announces
/// them when they appear.
class LpgBanner extends StatelessWidget {
  const LpgBanner({
    super.key,
    required this.message,
    this.title,
    this.tone = LpgTone.info,
    this.icon,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final String? title;
  final LpgTone tone;
  final IconData? icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  IconData get _defaultIcon => switch (tone) {
    LpgTone.danger => LpgIcons.error,
    LpgTone.warning => LpgIcons.warning,
    LpgTone.success => LpgIcons.success,
    _ => LpgIcons.info,
  };

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final fg = tone.foreground(colors);

    return Semantics(
      liveRegion: tone == LpgTone.danger || tone == LpgTone.warning,
      container: true,
      child: Container(
        padding: const EdgeInsets.all(LpgSpacing.md),
        decoration: BoxDecoration(
          color: tone.container(colors),
          borderRadius: BorderRadius.circular(LpgRadius.lg),
          border: Border.all(
            color: colors.isHighContrast ? fg : fg.withValues(alpha: 0.25),
            width: colors.isHighContrast ? 2 : 1,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon ?? _defaultIcon, color: fg, size: LpgSizes.iconMd),
            const SizedBox(width: LpgSpacing.smd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (title != null) ...[
                    Text(
                      title!,
                      style: text.titleSmall?.copyWith(
                        color: colors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: LpgSpacing.xs / 2),
                  ],
                  Text(
                    message,
                    style: text.bodyMedium?.copyWith(color: colors.textPrimary),
                  ),
                  if (actionLabel != null && onAction != null)
                    Padding(
                      padding: const EdgeInsets.only(top: LpgSpacing.xs),
                      child: TextButton(
                        onPressed: onAction,
                        style: TextButton.styleFrom(
                          foregroundColor: fg,
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(0, LpgSizes.touchTarget),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        child: Text(actionLabel!),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
