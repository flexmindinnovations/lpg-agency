import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

import '../device_access.dart';
import '../device_strings.dart';

/// "Waiting for approval": shown when the agency has not approved this phone
/// yet. It asks the server again every [pollInterval] while it is on screen
/// and on the button, and the router moves on by itself once the phone is
/// approved.
class WaitingForApprovalScreen extends StatefulWidget {
  const WaitingForApprovalScreen({
    super.key,
    required this.strings,
    required this.phoneName,
    required this.controller,
    required this.onSignOut,
    this.pollInterval = const Duration(seconds: 15),
  });

  final DeviceStrings strings;
  final String phoneName;
  final DeviceAccessController controller;
  final VoidCallback onSignOut;
  final Duration pollInterval;

  @override
  State<WaitingForApprovalScreen> createState() =>
      _WaitingForApprovalScreenState();
}

class _WaitingForApprovalScreenState extends State<WaitingForApprovalScreen> {
  Timer? _timer;
  bool _checkedByHand = false;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChanged);
    _timer = Timer.periodic(
      widget.pollInterval,
      (_) => widget.controller.refresh(),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    widget.controller.removeListener(_onChanged);
    super.dispose();
  }

  void _onChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _checkAgain() async {
    setState(() => _checkedByHand = true);
    await widget.controller.refresh();
  }

  @override
  Widget build(BuildContext context) {
    final strings = widget.strings;
    final text = context.lpgText;
    final colors = context.lpgColors;
    final checking = widget.controller.isChecking;
    final stillWaiting =
        _checkedByHand &&
        !checking &&
        widget.controller.access == DeviceAccess.pending;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: LpgEmptyState(
                title: strings.waitingTitle,
                message: strings.waitingMessage,
                icon: LpgIcons.pending,
                tone: LpgTone.warning,
                actionLabel: strings.waitingCheckAgain,
                actionIcon: LpgIcons.sync,
                onAction: checking ? null : _checkAgain,
              ),
            ),
            Padding(
              padding: LpgSpacing.page,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      stillWaiting ? strings.waitingStillWaiting : '',
                      textAlign: TextAlign.center,
                      style: text.bodyMedium?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                  ),
                  const SizedBox(height: LpgSpacing.sm),
                  Text(
                    strings.waitingPhoneLabel,
                    style: text.labelMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  Text(widget.phoneName, style: text.titleSmall),
                  const SizedBox(height: LpgSpacing.md),
                  LpgButton(
                    label: strings.waitingSignOut,
                    variant: LpgButtonVariant.text,
                    icon: LpgIcons.logout,
                    onPressed: widget.onSignOut,
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
