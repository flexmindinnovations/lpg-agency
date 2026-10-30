import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../fleet/presentation/document_photo_field.dart';
import 'compliance_presentation.dart';

/// One document: whose it is, its number and dates and whether it has been
/// verified, with a Renew button that swaps in the renewal form. Pops the
/// renewed [ComplianceDocument].
class ComplianceDocumentSheet extends ConsumerStatefulWidget {
  const ComplianceDocumentSheet({
    super.key,
    required this.document,
    required this.ownerName,
  });

  final ComplianceDocument document;
  final String ownerName;

  @override
  ConsumerState<ComplianceDocumentSheet> createState() =>
      _ComplianceDocumentSheetState();
}

class _ComplianceDocumentSheetState
    extends ConsumerState<ComplianceDocumentSheet> {
  late final _number = TextEditingController(
    text: widget.document.documentNumber,
  );
  bool _renewing = false;
  bool _busy = false;
  String? _fileRef;
  DateTime? _issued;
  DateTime? _expires;
  String? _error;

  @override
  void dispose() {
    _number.dispose();
    super.dispose();
  }

  Future<void> _renew() async {
    final doc = widget.document;
    final number = _number.text.trim();
    final needsExpiry = docTypeNeedsExpiry(doc.docType);
    final String? problem;
    if (_fileRef == null) {
      problem = 'Add a photo of the renewed document.';
    } else if (number.isEmpty) {
      problem = 'Enter the document number.';
    } else if (needsExpiry && _expires == null) {
      problem = 'Pick the new expiry date.';
    } else if (needsExpiry &&
        _expires != null &&
        !_expires!.isAfter(DateTime.now())) {
      problem = 'The new expiry date must be in the future.';
    } else {
      problem = null;
    }
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(fleetApiProvider)
        .renewDocument(
          doc.id,
          documentNumber: number,
          fileRef: _fileRef!,
          issueDate: _issued,
          expiryDate: _expires,
        );
    if (!mounted) return;
    switch (result) {
      case Success<ComplianceDocument>(:final value):
        Navigator.of(context).pop(value);
      case FailureResult<ComplianceDocument>(:final failure):
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
    final days = doc.daysLeft();
    final tone = days == null ? LpgTone.neutral : urgencyFor(days).tone;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            widget.ownerName,
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          if (days != null)
            LpgBanner(
              tone: tone,
              icon: days < 0 ? LpgIcons.blocked : LpgIcons.clock,
              message: dueLabel(days),
            ),
          if (!_renewing) ...[
            const SizedBox(height: LpgSpacing.md),
            LpgGroupedList(
              children: [
                LpgListTile(
                  title: 'Number',
                  trailing: Text(doc.documentNumber, style: text.titleSmall),
                ),
                if (doc.issueDate != null)
                  LpgListTile(
                    title: 'Issued',
                    trailing: Text(
                      LpgFormat.date(doc.issueDate!),
                      style: text.titleSmall,
                    ),
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
                  title: 'Checked by the office',
                  trailing: LpgStatusBadge(
                    label: verificationLabel(doc.verificationStatus),
                    severity: verificationSeverity(doc.verificationStatus),
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
            const SizedBox(height: LpgSpacing.lg),
            LpgButton(
              label: 'Renew',
              icon: LpgIcons.refill,
              expand: true,
              onPressed: () => setState(() => _renewing = true),
            ),
          ] else ...[
            const SizedBox(height: LpgSpacing.md),
            DocumentPhotoField(
              label: 'Photo of the renewed document',
              onUploaded: (ref) => setState(() => _fileRef = ref),
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgTextField(
              label: 'Document number',
              controller: _number,
              textCapitalization: TextCapitalization.characters,
              enabled: !_busy,
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgDateField(
              label: 'Issued on (optional)',
              value: _issued,
              lastDate: DateTime.now(),
              onChanged: (d) => setState(() => _issued = d),
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgDateField(
              label: 'New expiry date',
              isRequired: docTypeNeedsExpiry(doc.docType),
              value: _expires,
              firstDate: DateTime.now(),
              onChanged: (d) => setState(() => _expires = d),
            ),
            if (_error != null) ...[
              const SizedBox(height: LpgSpacing.sm),
              LpgBanner(tone: LpgTone.danger, message: _error!),
            ],
            const SizedBox(height: LpgSpacing.lg),
            LpgButton(
              label: 'Save renewal',
              icon: LpgIcons.check,
              isLoading: _busy,
              expand: true,
              onPressed: _busy ? null : _renew,
            ),
            const SizedBox(height: LpgSpacing.sm),
            LpgButton(
              label: 'Back',
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: _busy ? null : () => setState(() => _renewing = false),
            ),
          ],
        ],
      ),
    );
  }
}
