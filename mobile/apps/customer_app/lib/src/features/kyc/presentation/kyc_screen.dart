import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/kyc_provider.dart';

/// Human-readable label for a `doc_type` value ("aadhaar" -> "Aadhaar
/// Card") -- mirrors [SubmitKycScreen]'s own picker options, but a document
/// submitted before this screen existed (or by a future doc type this app
/// doesn't yet offer in the picker) can carry any lowercase string
/// server-side (`domain/customer/customer.py` only requires non-empty), so
/// this falls back to a title-cased render of whatever's there instead of
/// assuming it's one of the known values.
String _docTypeLabel(String docType) => switch (docType) {
  'aadhaar' => 'Aadhaar Card',
  'pan' => 'PAN Card',
  'voter_id' => 'Voter ID',
  'driving_license' => 'Driving License',
  'passport' => 'Passport',
  _ when docType.isEmpty => 'Document',
  _ => docType[0].toUpperCase() + docType.substring(1).replaceAll('_', ' '),
};

/// Masks a document number for display, keeping only the last 4 characters
/// visible (e.g. Aadhaar's 12 digits -> "•••• •••• 1234") -- shown inside
/// the customer's own app, but KYC numbers are sensitive enough to not
/// print in full on a screen that could be shoulder-surfed or screen-
/// recorded regardless of who's looking at it.
String _maskDocumentNumber(String number) {
  if (number.length <= 4) return number;
  final visible = number.substring(number.length - 4);
  return '${'•' * (number.length - 4)} $visible';
}

({String label, LpgStatusSeverity severity, IconData icon}) _statusDisplay(
  String status,
) => switch (status) {
  'verified' => (
    label: 'Verified',
    severity: LpgStatusSeverity.success,
    icon: LpgIcons.verified,
  ),
  'rejected' => (
    label: 'Rejected',
    severity: LpgStatusSeverity.danger,
    icon: LpgIcons.error,
  ),
  _ => (
    label: 'Pending Review',
    severity: LpgStatusSeverity.warning,
    icon: LpgIcons.pending,
  ),
};

class KycScreen extends ConsumerWidget {
  const KycScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docsAsync = ref.watch(kycDocumentsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('KYC Documents')),
      body: docsAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 3),
        error: (err, _) => LpgErrorState(
          message: 'Failed to load your KYC documents\n$err',
          onRetry: () => ref.refresh(kycDocumentsProvider),
        ),
        data: (docs) {
          if (docs.isEmpty) {
            return LpgEmptyState(
              title: 'Verify your identity',
              message:
                  "You haven't submitted any KYC documents yet. Verified "
                  "identity documents help us process your orders faster.",
              icon: LpgIcons.kyc,
              actionLabel: 'Add Document',
              actionIcon: LpgIcons.add,
              onAction: () => context.push('/profile/kyc/new'),
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(kycDocumentsProvider.future),
            child: ListView(
              padding: LpgSpacing.page,
              children: [
                for (final (i, doc) in docs.indexed) ...[
                  LpgFadeSlideIn(
                    index: i,
                    child: _KycDocumentCard(doc: doc),
                  ),
                  const SizedBox(height: LpgSpacing.smd),
                ],
                const SizedBox(height: LpgSpacing.sm),
                LpgButton(
                  label: 'Add Another Document',
                  variant: LpgButtonVariant.secondary,
                  expand: true,
                  icon: LpgIcons.add,
                  onPressed: () => context.push('/profile/kyc/new'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _KycDocumentCard extends StatelessWidget {
  const _KycDocumentCard({required this.doc});

  final KycDocumentResponse doc;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final status = _statusDisplay(doc.verificationStatus);
    const thumb = LpgSizes.iconBox + LpgSpacing.sm;

    final placeholder = LpgIconBox(
      icon: LpgIcons.kyc,
      tone: status.severity.tone,
      size: thumb,
    );

    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (doc.fileUrl != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(LpgRadius.lg),
                  child: Image.network(
                    doc.fileUrl!,
                    width: thumb,
                    height: thumb,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) => LpgIconBox(
                      icon: LpgIcons.imageBroken,
                      tone: LpgTone.neutral,
                      size: thumb,
                    ),
                  ),
                )
              else
                placeholder,
              const SizedBox(width: LpgSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_docTypeLabel(doc.docType), style: text.titleSmall),
                    const SizedBox(height: LpgSpacing.xs / 2),
                    Text(
                      _maskDocumentNumber(doc.documentNumber),
                      style: text.bodySmall,
                    ),
                  ],
                ),
              ),
              LpgStatusBadge(
                label: status.label,
                severity: status.severity,
                icon: status.icon,
              ),
            ],
          ),
          if (doc.verificationStatus == 'rejected' &&
              doc.rejectionReason != null) ...[
            const SizedBox(height: LpgSpacing.md),
            LpgBanner(tone: LpgTone.danger, message: doc.rejectionReason!),
          ],
          if (doc.verifiedAt != null) ...[
            const SizedBox(height: LpgSpacing.smd),
            Text(
              'Verified on ${LpgFormat.date(doc.verifiedAt!)}',
              style: text.bodySmall?.copyWith(color: colors.statusSuccess),
            ),
          ],
        ],
      ),
    );
  }
}
