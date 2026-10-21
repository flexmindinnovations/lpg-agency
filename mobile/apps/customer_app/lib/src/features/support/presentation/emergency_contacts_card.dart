import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/complaints_provider.dart';

/// "Smell gas?" — the LPG emergency helpline (1906 unless the agency set
/// another) with the safety steps, plus a call button for the agency. Shown
/// at the top of Support and inside the gas-leak complaint form.
class EmergencyContactsCard extends ConsumerWidget {
  const EmergencyContactsCard({super.key});

  static const helplineButtonKey = Key('emergency-helpline-call');
  static const agencyButtonKey = Key('agency-call');

  Future<void> _call(BuildContext context, String number) async {
    final ok = await launchUrl(Uri(scheme: 'tel', path: number));
    if (!ok && context.mounted) {
      LpgFeedback.showToast(
        context,
        "Couldn't start a call. Dial $number.",
        tone: LpgTone.warning,
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final contacts = ref.watch(supportContactsProvider).value;
    final helpline = contacts?.emergencyHelpline ?? lpgEmergencyHelpline;
    final agency = contacts?.agencyPhone;

    return LpgCard(
      variant: LpgCardVariant.outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const LpgIconBox(icon: LpgIcons.warning, tone: LpgTone.danger),
              const SizedBox(width: LpgSpacing.smd),
              Expanded(
                child: Text(
                  'Smell gas?',
                  style: text.titleMedium?.copyWith(color: colors.statusDanger),
                ),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.sm),
          Text(
            'Turn off the regulator, open doors and windows, and do not '
            'switch on lights or appliances. Then call the LPG emergency '
            'helpline from outside.',
            style: text.bodyMedium,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgButton(
            key: helplineButtonKey,
            label: 'Call $helpline (emergency)',
            icon: LpgIcons.call,
            variant: LpgButtonVariant.destructive,
            expand: true,
            onPressed: () => _call(context, helpline),
          ),
          if (agency != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgButton(
              key: agencyButtonKey,
              label: 'Call your agency',
              icon: LpgIcons.phone,
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: () => _call(context, agency),
            ),
          ],
        ],
      ),
    );
  }
}
