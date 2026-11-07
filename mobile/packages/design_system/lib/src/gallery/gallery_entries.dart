import 'package:flutter/material.dart';

import '../components/components.dart';
import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import '../tone.dart';

/// One named group of components in the gallery.
class GalleryEntry {
  const GalleryEntry(this.name, this.builder);

  /// File-safe: it becomes a golden file name.
  final String name;
  final WidgetBuilder builder;
}

const _gap = SizedBox(height: LpgSpacing.md);

void _noop() {}

/// Every group, in the order the gallery shows them.
final List<GalleryEntry> galleryEntries = [
  GalleryEntry('buttons', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final v in LpgButtonVariant.values) ...[
          LpgButton(
            label: v.name,
            icon: LpgIcons.check,
            variant: v,
            onPressed: _noop,
          ),
          _gap,
        ],
        const LpgButton(label: 'Disabled', onPressed: null),
        _gap,
        const LpgButton(label: 'Loading', isLoading: true, onPressed: _noop),
        _gap,
        const LpgButton(
          label: 'Large',
          icon: LpgIcons.navigate,
          size: LpgButtonSize.large,
          onPressed: _noop,
        ),
      ],
    );
  }),
  GalleryEntry('action_row', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgActionRow(
          children: [
            LpgButton(
              label: 'Dispute',
              variant: LpgButtonVariant.destructive,
              onPressed: _noop,
            ),
            LpgButton(label: 'Accept & Verify', onPressed: _noop),
          ],
        ),
        _gap,
        LpgActionRow(
          children: [
            LpgButton(
              label: 'Cancel',
              variant: LpgButtonVariant.text,
              onPressed: _noop,
            ),
            LpgButton(
              label: 'Discard',
              variant: LpgButtonVariant.secondary,
              icon: LpgIcons.delete,
              onPressed: _noop,
            ),
            LpgButton(label: 'Retry', icon: LpgIcons.sync, onPressed: _noop),
          ],
        ),
      ],
    );
  }),
  GalleryEntry('fields', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const LpgTextField(
          label: 'Phone number',
          hintText: '10-digit mobile number',
          prefixIcon: LpgIcons.phone,
          isRequired: true,
        ),
        _gap,
        const LpgTextField(
          label: 'With a value',
          initialValue: 'Plot 12, Basheerbagh',
        ),
        _gap,
        const LpgTextField(
          label: 'With an error',
          initialValue: '123',
          errorText: 'Enter a 10-digit number.',
        ),
        _gap,
        const LpgTextField(
          label: 'Disabled',
          initialValue: 'Cannot edit',
          enabled: false,
        ),
        _gap,
        LpgDropdownField<String>(
          label: 'State',
          value: 'tg',
          items: const {'tg': 'Telangana', 'ap': 'Andhra Pradesh'},
          onChanged: (_) {},
        ),
        _gap,
        LpgChoiceChips<String>(
          options: const {'a': 'Delivery', 'b': 'Billing', 'c': 'Both'},
          selected: 'a',
          onSelected: (_) {},
        ),
        _gap,
        LpgQuantityStepper(value: 2, min: 1, max: 5, onChanged: (_) {}),
      ],
    );
  }),
  GalleryEntry('status_and_banners', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: LpgSpacing.sm,
          runSpacing: LpgSpacing.sm,
          children: [
            for (final s in LpgStatusSeverity.values)
              LpgStatusBadge(label: s.name, severity: s),
          ],
        ),
        _gap,
        for (final tone in [
          LpgTone.info,
          LpgTone.success,
          LpgTone.warning,
          LpgTone.danger,
        ]) ...[
          LpgBanner(
            tone: tone,
            title: tone.name,
            message: 'A message that explains what happened.',
            actionLabel: 'Fix it',
            onAction: _noop,
          ),
          _gap,
        ],
      ],
    );
  }),
  GalleryEntry('illustrated_tiles', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Expanded(
              child: LpgMetricTile(
                label: 'Expected',
                value: '₹1,24,500',
                caption: '3 handovers',
                icon: LpgIcons.handover,
                illustration: LpgIllustration.banknotes,
              ),
            ),
            const SizedBox(width: LpgSpacing.smd),
            const Expanded(
              child: LpgMetricTile(
                label: 'Handed over',
                value: '₹1,19,000',
                icon: LpgIcons.cash,
                tone: LpgTone.success,
                illustration: LpgIllustration.cashReceived,
              ),
            ),
          ],
        ),
        const SizedBox(height: LpgSpacing.smd),
        const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: LpgMetricTile(
                label: 'Short',
                value: '₹5,500',
                icon: LpgIcons.warning,
                tone: LpgTone.danger,
                attention: true,
                illustration: LpgIllustration.shortfall,
              ),
            ),
            SizedBox(width: LpgSpacing.smd),
            Expanded(
              child: LpgMetricTile(
                label: 'Excess',
                value: '₹0',
                icon: LpgIcons.trendUp,
                tone: LpgTone.info,
                illustration: LpgIllustration.excess,
              ),
            ),
          ],
        ),
      ],
    );
  }),
  GalleryEntry('cards_and_tiles', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final v in LpgCardVariant.values) ...[
          LpgCard(variant: v, child: Text('${v.name} card')),
          _gap,
        ],
        Row(
          children: [
            Expanded(
              child: LpgMetricTile(
                label: 'Awaiting confirmation',
                value: '13',
                icon: LpgIcons.orders,
                tone: LpgTone.warning,
                caption: '4 to review',
                attention: true,
                onTap: _noop,
              ),
            ),
            const SizedBox(width: LpgSpacing.smd),
            const Expanded(
              child: LpgMetricTile(
                label: 'Out for delivery',
                value: '₹2,717',
                icon: LpgIcons.truck,
                caption: 'Collected today',
              ),
            ),
          ],
        ),
        _gap,
        const LpgStatTile(
          label: 'Delivered',
          value: '12',
          icon: LpgIcons.success,
          tone: LpgTone.success,
        ),
        _gap,
        LpgActionCard(
          icon: LpgIcons.truck,
          title: 'On its way',
          message: 'ORD000060 is out for delivery',
          actionLabel: 'Track',
          onTap: _noop,
        ),
        _gap,
        Row(
          children: [
            for (final (i, a) in [
              (LpgIcons.invoice, 'Invoices'),
              (LpgIcons.payment, 'Payments'),
              (LpgIcons.support, 'Get help'),
            ].indexed) ...[
              if (i > 0) const SizedBox(width: LpgSpacing.sm),
              Expanded(
                child: LpgQuickAction(
                  icon: a.$1,
                  label: a.$2,
                  tone: LpgTone.values[i],
                  onTap: _noop,
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }),
  GalleryEntry('hero', (context) {
    return LpgHeroCard(
      watermark: LpgIcons.cylinder,
      keepClearOfWatermark: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Empty cylinders with you'),
          const SizedBox(height: LpgSpacing.sm),
          Text(
            '3',
            style: context.lpgText.displayLarge?.copyWith(
              color: context.lpgColors.onHero,
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgHeroStats(
            stats: const [
              LpgHeroStat(value: '1', label: 'On the way'),
              LpgHeroStat(value: '24', label: 'Orders placed'),
            ],
          ),
        ],
      ),
    );
  }),
  GalleryEntry('lists', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgSectionHeader(
          title: 'Recent orders',
          actionLabel: 'See all',
          onAction: _noop,
          padding: EdgeInsets.zero,
        ),
        _gap,
        LpgGroupedList(
          children: [
            LpgListTile(
              leadingIcon: LpgIcons.success,
              leadingTone: LpgTone.success,
              title: 'ORD000061',
              subtitle: '29 Oct',
              trailing: const LpgStatusBadge(
                label: 'Closed',
                severity: LpgStatusSeverity.success,
              ),
              showChevron: true,
              onTap: _noop,
            ),
            LpgListTile(
              leadingIcon: LpgIcons.truck,
              leadingTone: LpgTone.warning,
              title: 'ORD000060',
              subtitle: '5 Sep',
              trailing: const LpgStatusBadge(
                label: 'Out for delivery',
                severity: LpgStatusSeverity.warning,
              ),
              showChevron: true,
              onTap: _noop,
            ),
            LpgListTile(
              leading: const LpgAvatar(name: 'Vilas Rakhe'),
              title: 'Vilas Rakhe',
              subtitle: 'CN-E2E-098 · +919999900098',
              showChevron: true,
              onTap: _noop,
            ),
          ],
        ),
        _gap,
        const LpgCard(
          child: Column(
            children: [
              LpgKeyValueRow(label: 'Amount due', value: '₹1,200.00'),
              LpgKeyValueRow(
                label: 'Total',
                value: '₹2,400.00',
                emphasize: true,
              ),
            ],
          ),
        ),
      ],
    );
  }),
  GalleryEntry('timeline', (context) {
    return const LpgCard(
      child: LpgTimeline(
        steps: [
          LpgTimelineStep(
            title: 'Order placed',
            subtitle: '29 Oct, 10:02',
            state: LpgTimelineState.done,
          ),
          LpgTimelineStep(
            title: 'Out for delivery',
            subtitle: 'Driver is on the way',
            state: LpgTimelineState.current,
          ),
          LpgTimelineStep(title: 'Delivered', state: LpgTimelineState.upcoming),
        ],
      ),
    );
  }),
  GalleryEntry('states', (context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const LpgEmptyState(
          title: 'No recent orders',
          message: 'Your refills will show up here.',
          icon: LpgIcons.orders,
        ),
        _gap,
        LpgErrorState(
          message: 'Could not load your profile.',
          onRetry: _noop,
          supportCode: 'ERR-1042',
        ),
      ],
    );
  }),
  GalleryEntry('navigation', (context) {
    return LpgNavigationBar(
      selectedIndex: 0,
      onDestinationSelected: (_) {},
      destinations: const [
        LpgNavDestination(
          icon: LpgIcons.home,
          selectedIcon: LpgIcons.home,
          label: 'Home',
        ),
        LpgNavDestination(
          icon: LpgIcons.orders,
          selectedIcon: LpgIcons.orders,
          label: 'Orders',
          badgeCount: 3,
        ),
        LpgNavDestination(
          icon: LpgIcons.support,
          selectedIcon: LpgIcons.support,
          label: 'Support',
        ),
      ],
    );
  }),
];
