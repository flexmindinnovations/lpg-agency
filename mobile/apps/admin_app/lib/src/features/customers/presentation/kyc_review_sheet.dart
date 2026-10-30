import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';

LpgStatusSeverity kycSeverity(String status) => switch (status) {
  'verified' => LpgStatusSeverity.success,
  'rejected' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.warning,
};

String kycStatusLabel(String status) => switch (status) {
  'verified' => 'Verified',
  'rejected' => 'Rejected',
  'expired' => 'Expired',
  _ => 'Waiting for review',
};

/// A customer's identity document: its details and, while it is waiting for
/// review, Verify and Reject. Pops `verified` or `rejected`.
class KycReviewSheet extends ConsumerStatefulWidget {
  const KycReviewSheet({
    super.key,
    required this.customerId,
    required this.document,
  });

  final String customerId;
  final KycDocumentResponse document;

  @override
  ConsumerState<KycReviewSheet> createState() => _KycReviewSheetState();
}

class _KycReviewSheetState extends ConsumerState<KycReviewSheet> {
  final _reason = TextEditingController();
  bool _rejecting = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _decide(bool verified) async {
    final reason = _reason.text.trim();
    if (!verified && reason.length < 3) {
      setState(
        () => _error = 'Say why, so the customer knows what to send again.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(kycApiProvider)
        .verifyDocument(
          widget.customerId,
          widget.document.id,
          verified: verified,
          reason: verified ? null : reason,
        );
    if (!mounted) return;
    switch (result) {
      case Success<void>():
        Navigator.of(context).pop(verified ? 'verified' : 'rejected');
      case FailureResult<void>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final doc = widget.document;
    final text = context.lpgText;
    final colors = context.lpgColors;
    final waiting = doc.verificationStatus == 'pending';
    final fileUrl = doc.fileUrl;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (fileUrl != null && fileUrl.isNotEmpty) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(LpgRadius.lg),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 220),
                child: Image.network(
                  fileUrl,
                  fit: BoxFit.contain,
                  errorBuilder: (_, _, _) => LpgBanner(
                    tone: LpgTone.warning,
                    icon: LpgIcons.imageBroken,
                    message: 'The photo could not be shown.',
                  ),
                ),
              ),
            ),
            const SizedBox(height: LpgSpacing.md),
          ],
          LpgGroupedList(
            children: [
              LpgListTile(
                title: 'Number',
                trailing: Text(doc.documentNumber, style: text.titleSmall),
              ),
              if (doc.expiryDate != null)
                LpgListTile(
                  title: 'Expires',
                  trailing: Text(
                    LpgFormat.date(doc.expiryDate!),
                    style: text.titleSmall,
                  ),
                ),
              LpgListTile(
                title: 'Status',
                trailing: LpgStatusBadge(
                  label: kycStatusLabel(doc.verificationStatus),
                  severity: kycSeverity(doc.verificationStatus),
                ),
              ),
            ],
          ),
          if (doc.rejectionReason != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(
              tone: LpgTone.danger,
              title: 'Rejected',
              message: doc.rejectionReason!,
            ),
          ],
          if (waiting) ...[
            if (_rejecting) ...[
              const SizedBox(height: LpgSpacing.md),
              LpgTextField(
                label: 'Why is it being rejected',
                hintText: 'The photo is blurred, the name does not match…',
                controller: _reason,
                maxLines: 3,
                enabled: !_busy,
                textCapitalization: TextCapitalization.sentences,
              ),
            ] else ...[
              const SizedBox(height: LpgSpacing.sm),
              Text(
                'Check the photo against the number before verifying.',
                style: text.bodySmall?.copyWith(color: colors.textSecondary),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: LpgSpacing.sm),
              LpgBanner(tone: LpgTone.danger, message: _error!),
            ],
            const SizedBox(height: LpgSpacing.lg),
            if (_rejecting) ...[
              LpgButton(
                label: 'Reject document',
                icon: LpgIcons.close,
                isLoading: _busy,
                expand: true,
                onPressed: _busy ? null : () => _decide(false),
              ),
              const SizedBox(height: LpgSpacing.sm),
              LpgButton(
                label: 'Back',
                variant: LpgButtonVariant.secondary,
                expand: true,
                onPressed: _busy
                    ? null
                    : () => setState(() => _rejecting = false),
              ),
            ] else ...[
              LpgButton(
                label: 'Verify document',
                icon: LpgIcons.verified,
                isLoading: _busy,
                expand: true,
                onPressed: _busy ? null : () => _decide(true),
              ),
              const SizedBox(height: LpgSpacing.sm),
              LpgButton(
                label: 'Reject',
                variant: LpgButtonVariant.secondary,
                expand: true,
                onPressed: _busy
                    ? null
                    : () => setState(() => _rejecting = true),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
