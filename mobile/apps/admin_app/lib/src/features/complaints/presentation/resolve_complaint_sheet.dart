import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import 'complaint_presentation.dart';

/// Closes a complaint with an outcome and a note on what was done. Pops
/// `true` once it is resolved.
class ResolveComplaintSheet extends ConsumerStatefulWidget {
  const ResolveComplaintSheet({super.key, required this.complaint});

  final ComplaintResponse complaint;

  @override
  ConsumerState<ResolveComplaintSheet> createState() =>
      _ResolveComplaintSheetState();
}

class _ResolveComplaintSheetState extends ConsumerState<ResolveComplaintSheet> {
  final _notes = TextEditingController();
  String _outcome = 'Resolved';
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final notes = _notes.text.trim();
    if (notes.isEmpty) {
      setState(() => _error = 'Say what was done, so it is on record.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(complaintApiProvider)
        .resolve(widget.complaint.id, outcome: _outcome, notes: notes);
    if (!mounted) return;
    switch (result) {
      case Success<void>():
        Navigator.of(context).pop(true);
      case FailureResult<void>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${complaintCategoryLabel(widget.complaint.category)}'
            '${widget.complaint.complaintNumber == null ? '' : ' · ${widget.complaint.complaintNumber}'}',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          Text('Outcome', style: text.titleSmall),
          const SizedBox(height: LpgSpacing.sm),
          LpgChoiceChips<String>(
            options: resolutionOutcomes,
            selected: _outcome,
            onSelected: (v) {
              if (!_busy && v != null) setState(() => _outcome = v);
            },
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'What was done',
            hintText: 'Replaced the cylinder, refunded the extra charge…',
            controller: _notes,
            maxLines: 4,
            maxLength: 2000,
            enabled: !_busy,
            textCapitalization: TextCapitalization.sentences,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Resolve complaint',
            icon: LpgIcons.check,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}
