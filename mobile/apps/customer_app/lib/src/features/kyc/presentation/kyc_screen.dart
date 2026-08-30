import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

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
    icon: Icons.verified_outlined,
  ),
  'rejected' => (
    label: 'Rejected',
    severity: LpgStatusSeverity.danger,
    icon: Icons.error_outline,
  ),
  _ => (
    label: 'Pending Review',
    severity: LpgStatusSeverity.warning,
    icon: Icons.pending_actions_outlined,
  ),
};

class KycScreen extends ConsumerWidget {
  const KycScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docsAsync = ref.watch(kycDocumentsProvider);
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'KYC Documents',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: docsAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Failed to load your KYC documents\n$err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(kycDocumentsProvider),
        ),
        data: (docs) {
          if (docs.isEmpty) {
            return LpgEmptyState(
              message:
                  "You haven't submitted any KYC documents yet. Verified "
                  "identity documents help us process your orders faster.",
              icon: Icons.badge_outlined,
              actionLabel: 'Add Document',
              onAction: () => context.push('/profile/kyc/new'),
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(kycDocumentsProvider.future),
            child: ListView(
              padding: const EdgeInsets.all(24.0),
              children: [
                for (final doc in docs) ...[
                  _KycDocumentCard(doc: doc),
                  const SizedBox(height: 16),
                ],
                const SizedBox(height: 8),
                LpgButton(
                  label: 'Add Another Document',
                  variant: LpgButtonVariant.secondary,
                  expand: true,
                  icon: Icons.add,
                  onPressed: () => context.push('/profile/kyc/new'),
                ),
                const SizedBox(height: 24),
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
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final status = _statusDisplay(doc.verificationStatus);
    final statusColor = switch (status.severity) {
      LpgStatusSeverity.success => colors.statusSuccess,
      LpgStatusSeverity.warning => colors.statusWarning,
      LpgStatusSeverity.danger => colors.statusDanger,
      LpgStatusSeverity.info => colors.statusInfo,
      LpgStatusSeverity.neutral => colors.textSecondary,
    };

    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (doc.fileUrl != null) ...[
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.network(
                    doc.fileUrl!,
                    width: 48,
                    height: 48,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) => Container(
                      width: 48,
                      height: 48,
                      color: colors.surfaceRaised,
                      child: Icon(
                        Icons.image_not_supported_outlined,
                        color: colors.textSecondary,
                        size: 20,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
              ] else ...[
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: colors.surfaceRaised,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    Icons.badge_outlined,
                    color: colors.textSecondary,
                  ),
                ),
                const SizedBox(width: 16),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _docTypeLabel(doc.docType),
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: colors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _maskDocumentNumber(doc.documentNumber),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              LpgStatusBadge(label: status.label, severity: status.severity),
            ],
          ),
          if (doc.verificationStatus == 'rejected' &&
              doc.rejectionReason != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colors.statusDanger.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(status.icon, size: 16, color: statusColor),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      doc.rejectionReason!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: statusColor,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (doc.verifiedAt != null) ...[
            const SizedBox(height: 12),
            Text(
              'Verified on ${DateFormat('MMM dd, yyyy').format(doc.verifiedAt!)}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.textSecondary,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
