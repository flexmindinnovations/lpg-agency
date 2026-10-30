import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../orders/data/orders_provider.dart';
import 'stock_presentation.dart';

/// What approving a count does, in a sentence.
String countOutcome(ReconciliationRecord count) {
  final v = count.variance;
  if (v == 0) return 'The count matches the system, so stock stays as it is.';
  final n = v.abs();
  final cylinders = n == 1 ? 'cylinder' : 'cylinders';
  return v < 0
      ? 'Approving writes the stock down by $n $cylinders.'
      : 'Approving adds $n $cylinders to the stock.';
}

/// Lets someone other than the counter approve a count (booking its variance
/// into stock) or reject it with a reason (stock stays as it is). Pops
/// `approved` or `rejected`.
class CountReviewSheet extends ConsumerStatefulWidget {
  const CountReviewSheet({super.key, required this.count});

  final ReconciliationRecord count;

  @override
  ConsumerState<CountReviewSheet> createState() => _CountReviewSheetState();
}

class _CountReviewSheetState extends ConsumerState<CountReviewSheet> {
  final _reason = TextEditingController();
  bool _rejecting = false;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _decide(bool approve) async {
    final reason = _reason.text.trim();
    if (!approve && reason.length < 3) {
      setState(
        () => _error = 'Say why, so whoever counted knows what to redo.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(fleetApiProvider);
    final result = approve
        ? await api.approveCount(widget.count.id)
        : await api.rejectCount(widget.count.id, reason: reason);
    if (!mounted) return;
    switch (result) {
      case Success<ReconciliationRecord>():
        Navigator.of(context).pop(approve ? 'approved' : 'rejected');
      case FailureResult<ReconciliationRecord>(:final failure):
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
    final count = widget.count;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${names[count.cylinderTypeId] ?? 'Cylinder'} · ${stockStatusLabel(count.status)}',
            style: text.titleMedium,
          ),
          if (count.recordedAt != null)
            Text(
              'Counted ${LpgFormat.relative(count.recordedAt!)}',
              style: text.bodySmall?.copyWith(color: colors.textSecondary),
            ),
          const SizedBox(height: LpgSpacing.md),
          LpgGroupedList(
            children: [
              LpgListTile(
                title: 'System shows',
                trailing: Text(
                  '${count.expectedQuantity}',
                  style: text.titleSmall,
                ),
              ),
              LpgListTile(
                title: 'Counted',
                trailing: Text(
                  '${count.actualQuantity}',
                  style: text.titleSmall,
                ),
              ),
              LpgListTile(
                title: 'Difference',
                trailing: Text(
                  count.variance > 0
                      ? '+${count.variance}'
                      : '${count.variance}',
                  style: text.titleSmall?.copyWith(
                    color: count.variance < 0 ? colors.statusDanger : null,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          Text(
            countOutcome(count),
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          ),
          if (_rejecting) ...[
            const SizedBox(height: LpgSpacing.md),
            LpgTextField(
              label: 'Why is it being rejected',
              hintText: 'Recount the damaged cylinders…',
              controller: _reason,
              maxLines: 3,
              maxLength: 1000,
              enabled: !_busy,
              textCapitalization: TextCapitalization.sentences,
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          if (_rejecting) ...[
            LpgButton(
              label: 'Reject count',
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
              label: 'Approve count',
              icon: LpgIcons.check,
              isLoading: _busy,
              expand: true,
              onPressed: _busy ? null : () => _decide(true),
            ),
            const SizedBox(height: LpgSpacing.sm),
            LpgButton(
              label: 'Reject',
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: _busy ? null : () => setState(() => _rejecting = true),
            ),
          ],
        ],
      ),
    );
  }
}
