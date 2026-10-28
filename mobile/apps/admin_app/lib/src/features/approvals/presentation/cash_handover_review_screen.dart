import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../providers.dart';
import '../data/approvals_provider.dart';

class CashHandoverReviewScreen extends ConsumerStatefulWidget {
  const CashHandoverReviewScreen({
    super.key,
    required this.cashHandoverId,
    required this.driverName,
    required this.expectedAmount,
    required this.actualAmount,
    required this.shortfall,
    this.denominations,
    this.varianceReason,
    this.upiExpected,
  });

  final String cashHandoverId;
  final String driverName;
  final double expectedAmount;
  final double actualAmount;
  final double shortfall;

  /// Notes the driver counted, by denomination (ADR-066). Null when the
  /// driver typed a total instead.
  final Map<int, int>? denominations;
  final String? varianceReason;

  /// UPI the driver collected on the route; paid straight to the agency, so
  /// it is not part of the cash to hand over.
  final double? upiExpected;

  @override
  ConsumerState<CashHandoverReviewScreen> createState() =>
      _CashHandoverReviewScreenState();
}

class _CashHandoverReviewScreenState
    extends ConsumerState<CashHandoverReviewScreen> {
  final _noteController = TextEditingController();
  bool _loading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _submitReview(String outcome) async {
    final note = _noteController.text.trim();
    if (outcome == 'disputed' && note.isEmpty) {
      setState(
        () => _errorMessage =
            'A note is required when disputing a cash handover.',
      );
      return;
    }

    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    final adminApi = ref.read(adminApiProvider);
    final request = ReviewCashHandoverRequest(
      outcome: outcome,
      note: note.isEmpty ? null : note,
    );
    final result = await adminApi.reviewCashHandover(
      widget.cashHandoverId,
      request,
    );

    if (!mounted) return;

    result.when(
      onSuccess: (_) {
        LpgFeedback.showToast(
          context,
          'Cash handover review submitted ($outcome)',
        );
        ref.invalidate(pendingCashHandoversProvider);
        context.pop();
      },
      onFailure: (failure) {
        setState(() {
          _loading = false;
          _errorMessage = failure.message;
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Scaffold(
      appBar: AppBar(title: const Text('Reconcile Cash Handover')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: LpgSpacing.page,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_errorMessage != null) ...[
                LpgBanner(message: _errorMessage!, tone: LpgTone.danger),
                const SizedBox(height: LpgSpacing.md),
              ],
              LpgCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Driver: ${widget.driverName}',
                      style: text.titleMedium,
                    ),
                    const SizedBox(height: LpgSpacing.sm),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Expected Cash:', style: text.bodyMedium),
                        Text(
                          LpgFormat.currency(widget.expectedAmount),
                          style: text.titleSmall,
                        ),
                      ],
                    ),
                    const SizedBox(height: LpgSpacing.xs),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Actual Handed Over:', style: text.bodyMedium),
                        Text(
                          LpgFormat.currency(widget.actualAmount),
                          style: text.titleSmall?.copyWith(
                            color: colors.actionPrimary,
                          ),
                        ),
                      ],
                    ),
                    if (widget.shortfall > 0) ...[
                      const Divider(height: LpgSpacing.lg),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Shortfall Variance:',
                            style: text.bodyMedium?.copyWith(
                              color: colors.statusDanger,
                            ),
                          ),
                          Text(
                            LpgFormat.currency(widget.shortfall),
                            style: text.titleMedium?.copyWith(
                              color: colors.statusDanger,
                            ),
                          ),
                        ],
                      ),
                    ],
                    if ((widget.upiExpected ?? 0) > 0) ...[
                      const SizedBox(height: LpgSpacing.xs),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Paid by UPI (not cash):',
                            style: text.bodyMedium,
                          ),
                          Text(
                            LpgFormat.currency(widget.upiExpected!),
                            style: text.titleSmall,
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              if (widget.varianceReason case final reason?
                  when reason.isNotEmpty) ...[
                const SizedBox(height: LpgSpacing.md),
                LpgBanner(
                  tone: LpgTone.warning,
                  title: "Driver's reason for the difference",
                  message: reason,
                ),
              ],
              if (widget.denominations case final notes?
                  when notes.isNotEmpty) ...[
                const SizedBox(height: LpgSpacing.md),
                LpgCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Notes counted', style: text.titleSmall),
                      const SizedBox(height: LpgSpacing.sm),
                      for (final value in cashDenominations)
                        if ((notes[value] ?? 0) > 0)
                          Padding(
                            padding: const EdgeInsets.only(
                              bottom: LpgSpacing.xs,
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  '₹$value × ${notes[value]}',
                                  style: text.bodyMedium,
                                ),
                                Text(
                                  LpgFormat.currency(
                                    (value * notes[value]!).toDouble(),
                                  ),
                                  style: text.bodyMedium,
                                ),
                              ],
                            ),
                          ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                controller: _noteController,
                label: 'Reconciliation / Resolution Note',
                hintText:
                    'e.g., Shortfall deducted from driver allowance or verified cash count',
                maxLines: 3,
              ),
              const SizedBox(height: LpgSpacing.xxl),
              Row(
                children: [
                  Expanded(
                    child: LpgButton(
                      label: 'Dispute',
                      variant: LpgButtonVariant.destructive,
                      isLoading: _loading,
                      onPressed: _loading
                          ? null
                          : () => _submitReview('disputed'),
                    ),
                  ),
                  const SizedBox(width: LpgSpacing.md),
                  Expanded(
                    child: LpgButton(
                      label: 'Accept & Verify',
                      variant: LpgButtonVariant.primary,
                      isLoading: _loading,
                      onPressed: _loading
                          ? null
                          : () => _submitReview('accepted'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
