import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/complaints_provider.dart';
import 'complaint_presentation.dart';

class SupportScreen extends ConsumerWidget {
  const SupportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final complaintsAsync = ref.watch(complaintsProvider);
    final colors = context.lpgColors;
    final text = context.lpgText;

    final header = LpgHeroCard(
      watermark: LpgIcons.lifebuoy,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(LpgIcons.support, size: LpgSizes.iconXl, color: colors.onHero),
          const SizedBox(height: LpgSpacing.md),
          Text(
            'How can we help you?',
            style: text.titleLarge?.copyWith(color: colors.onHero),
          ),
          const SizedBox(height: LpgSpacing.xs),
          Text(
            'Our support team is available 24/7 for your assistance.',
            style: text.bodyMedium?.copyWith(
              color: colors.onHero.withValues(alpha: 0.85),
            ),
          ),
          const SizedBox(height: LpgSpacing.mdl),
          LpgButton(
            label: 'Raise a Complaint',
            icon: LpgIcons.complaint,
            variant: LpgButtonVariant.secondary,
            onPressed: () => context.push('/support/raise'),
            expand: true,
          ),
        ],
      ),
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Support Center')),
      body: RefreshIndicator(
        onRefresh: () async => ref.refresh(complaintsProvider.future),
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverPadding(
              padding: LpgSpacing.page.copyWith(bottom: 0),
              sliver: SliverList.list(
                children: [
                  LpgFadeSlideIn(child: header),
                  const LpgSectionHeader(title: 'Your Recent Tickets'),
                ],
              ),
            ),
            ...complaintsAsync.when(
              loading: () => const [
                SliverToBoxAdapter(child: LpgSkeletonList(itemCount: 3)),
              ],
              error: (err, stack) => [
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: LpgErrorState(
                    message: 'Failed to load tickets',
                    onRetry: () => ref.refresh(complaintsProvider),
                  ),
                ),
              ],
              data: (complaints) {
                if (complaints.isEmpty) {
                  return const [
                    SliverFillRemaining(
                      hasScrollBody: false,
                      child: LpgEmptyState(
                        message: 'No complaints raised yet.',
                        icon: LpgIcons.history,
                      ),
                    ),
                  ];
                }
                return [
                  SliverPadding(
                    padding: LpgSpacing.page.copyWith(top: 0),
                    sliver: SliverList.separated(
                      itemCount: complaints.length,
                      separatorBuilder: (context, index) =>
                          const SizedBox(height: LpgSpacing.sm),
                      itemBuilder: (context, index) {
                        final item = complaints[index];
                        final severity = complaintStatusSeverity(item.status);
                        return LpgFadeSlideIn(
                          index: index + 1,
                          child: LpgCard(
                            padding: EdgeInsets.zero,
                            onTap: () => context.push('/support/${item.id}'),
                            child: LpgListTile(
                              leadingIcon: LpgIcons.complaint,
                              leadingTone: severity.tone,
                              title: item.category,
                              subtitle:
                                  'Opened on ${LpgFormat.date(item.createdAt)}',
                              trailing: LpgStatusBadge(
                                label: item.status.toUpperCase(),
                                severity: severity,
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ];
              },
            ),
          ],
        ),
      ),
    );
  }
}
