import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/complaints_provider.dart';
import 'complaint_presentation.dart';
import 'emergency_contacts_card.dart';

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
            'Tell us about a delivery, billing or service problem and '
            'track it here.',
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
                  const LpgFadeSlideIn(child: EmergencyContactsCard()),
                  const SizedBox(height: LpgSpacing.md),
                  LpgFadeSlideIn(index: 1, child: header),
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
                    sliver: SliverToBoxAdapter(
                      child: LpgGroupedList(
                        staggerFrom: 1,
                        children: [
                          for (final item in complaints)
                            LpgListTile(
                              leadingIcon: LpgIcons.complaint,
                              leadingTone: complaintStatusSeverity(
                                item.status,
                              ).tone,
                              title: [
                                complaintCategoryLabel(item.category),
                                ?item.complaintNumber,
                              ].join(' · '),
                              subtitle:
                                  'Opened on ${LpgFormat.date(item.createdAt)}',
                              trailing: LpgStatusBadge(
                                label: humanizePascalCase(
                                  item.status,
                                ).toUpperCase(),
                                severity: complaintStatusSeverity(item.status),
                              ),
                              showChevron: true,
                              onTap: () => context.push('/support/${item.id}'),
                            ),
                        ],
                      ),
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
