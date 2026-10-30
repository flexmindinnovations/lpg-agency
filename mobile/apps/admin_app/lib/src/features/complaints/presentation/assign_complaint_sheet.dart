import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../data/complaints_provider.dart';

/// Picks the staff member who takes a complaint. Pops `true` once assigned.
class AssignComplaintSheet extends ConsumerStatefulWidget {
  const AssignComplaintSheet({super.key, required this.complaint});

  final ComplaintResponse complaint;

  @override
  ConsumerState<AssignComplaintSheet> createState() =>
      _AssignComplaintSheetState();
}

class _AssignComplaintSheetState extends ConsumerState<AssignComplaintSheet> {
  String? _selected;
  String? _error;
  bool _busy = false;

  Future<void> _submit() async {
    final id = _selected;
    if (id == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(complaintApiProvider)
        .assign(widget.complaint.id, id);
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
    final staffAsync = ref.watch(complaintAssigneesProvider);
    final text = context.lpgText;
    final colors = context.lpgColors;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'Who should take this complaint?',
          style: text.bodyMedium?.copyWith(color: colors.textSecondary),
        ),
        const SizedBox(height: LpgSpacing.md),
        staffAsync.when(
          loading: () => const Padding(
            padding: EdgeInsets.all(LpgSpacing.lg),
            child: Center(child: LpgLoadingIndicator()),
          ),
          error: (err, _) => LpgErrorState(
            message: errorMessage(err),
            onRetry: () => ref.invalidate(complaintAssigneesProvider),
          ),
          data: (staff) {
            if (staff.isEmpty) {
              return const LpgBanner(
                tone: LpgTone.warning,
                message: 'No staff can take complaints yet.',
              );
            }
            return ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: MediaQuery.sizeOf(context).height * 0.4,
              ),
              child: SingleChildScrollView(
                child: LpgGroupedList(
                  children: [
                    for (final s in staff)
                      LpgListTile(
                        leading: LpgAvatar(name: s.name),
                        title: s.name,
                        subtitle: LpgFormat.sentence(s.role),
                        trailing: _selected == s.userId
                            ? Icon(
                                LpgIcons.success,
                                color: colors.actionPrimary,
                              )
                            : null,
                        onTap: _busy
                            ? null
                            : () => setState(() => _selected = s.userId),
                      ),
                  ],
                ),
              ),
            );
          },
        ),
        if (_error != null) ...[
          const SizedBox(height: LpgSpacing.sm),
          LpgBanner(tone: LpgTone.danger, message: _error!),
        ],
        const SizedBox(height: LpgSpacing.lg),
        LpgButton(
          label: 'Assign',
          icon: LpgIcons.check,
          isLoading: _busy,
          expand: true,
          onPressed: _busy || _selected == null ? null : _submit,
        ),
      ],
    );
  }
}
