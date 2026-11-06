import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

import '../device_strings.dart';

/// "This phone is blocked": the agency has blocked (or removed) this phone.
/// The Driver app adds a line telling the driver that deliveries not yet sent
/// are safe on the phone.
class PhoneBlockedScreen extends StatelessWidget {
  const PhoneBlockedScreen({
    super.key,
    required this.strings,
    required this.onTryAgain,
  });

  final DeviceStrings strings;

  /// Leaves this screen for the sign-in screen (which asks the server again).
  final VoidCallback onTryAgain;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final kept = strings.blockedKeptWork;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: LpgEmptyState(
                title: strings.blockedTitle,
                message: strings.blockedMessage,
                icon: LpgIcons.blocked,
                tone: LpgTone.danger,
                actionLabel: strings.blockedTryAgain,
                actionIcon: LpgIcons.sync,
                onAction: onTryAgain,
              ),
            ),
            if (kept != null)
              Padding(
                padding: LpgSpacing.page,
                child: Text(
                  kept,
                  textAlign: TextAlign.center,
                  style: text.bodyMedium?.copyWith(color: colors.textSecondary),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
