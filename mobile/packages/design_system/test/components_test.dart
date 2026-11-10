import 'dart:convert';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: LpgTheme.light,
  home: Scaffold(body: Center(child: child)),
);

void main() {
  group('LpgButton', () {
    testWidgets('renders each variant and responds to taps', (tester) async {
      var tapped = false;
      for (final variant in LpgButtonVariant.values) {
        tapped = false;
        await tester.pumpWidget(
          _wrap(
            LpgButton(
              label: 'Go',
              variant: variant,
              onPressed: () => tapped = true,
            ),
          ),
        );
        await tester.tap(find.text('Go'));
        expect(tapped, isTrue, reason: 'variant $variant should be tappable');
      }
    });

    testWidgets('disables the button while loading', (tester) async {
      var tapped = false;
      await tester.pumpWidget(
        _wrap(
          LpgButton(
            label: 'Go',
            isLoading: true,
            onPressed: () => tapped = true,
          ),
        ),
      );
      // isLoading swaps the label for a spinner, so tap the whole button
      // area (its InkWell) rather than looking for the label text.
      await tester.tap(find.byType(InkWell));
      expect(tapped, isFalse);
    });

    testWidgets(
      'scales down on press and back up on release (spring press feedback)',
      (tester) async {
        await tester.pumpWidget(
          _wrap(LpgButton(label: 'Go', onPressed: () {})),
        );

        // `Transform.scale`'s matrix leaves the Z column untouched (it's a
        // 2D visual transform), so `Matrix4.getMaxScaleOnAxis()` always
        // reports 1.0 regardless of the real X/Y factor — read the m00
        // entry directly instead, which is exactly the `scale:` value
        // `Transform.scale` was built with.
        double scaleOf() => tester
            .widget<Transform>(
              find.ancestor(
                of: find.byType(InkWell),
                matching: find.byType(Transform),
              ),
            )
            .transform
            .storage[0];

        expect(scaleOf(), 1.0);

        final gesture = await tester.startGesture(
          tester.getCenter(find.byType(InkWell)),
        );
        // One frame for InkWell's own tap recognizer to resolve
        // onTapDown, then partway into the spring simulation — not the
        // full settle, just needs to have moved away from 1.0.
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        expect(scaleOf(), lessThan(1.0));

        await gesture.up();
        await tester.pumpAndSettle();
        expect(scaleOf(), closeTo(1.0, 0.001));
      },
    );
  });

  testWidgets('LpgCard renders its child', (tester) async {
    await tester.pumpWidget(_wrap(const LpgCard(child: Text('Inside'))));
    expect(find.text('Inside'), findsOneWidget);
  });

  testWidgets('LpgTextField shows label and validation error', (tester) async {
    final formKey = GlobalKey<FormState>();
    await tester.pumpWidget(
      _wrap(
        Form(
          key: formKey,
          child: LpgTextField(
            label: 'Phone',
            validator: (v) => (v == null || v.isEmpty) ? 'Required' : null,
          ),
        ),
      ),
    );
    expect(find.text('Phone'), findsOneWidget);
    formKey.currentState!.validate();
    await tester.pump();
    expect(find.text('Required'), findsOneWidget);
  });

  testWidgets('LpgTextField marks its label and shows an icon while invalid, '
      'and clears both as the user fixes the value', (tester) async {
    final formKey = GlobalKey<FormState>();
    await tester.pumpWidget(
      _wrap(
        Form(
          key: formKey,
          child: LpgTextField(
            label: 'Phone',
            validator: (v) => (v == null || v.isEmpty) ? 'Required' : null,
          ),
        ),
      ),
    );
    bool labelFlagged() =>
        tester.widget<LpgFieldLabel>(find.byType(LpgFieldLabel)).hasError;
    expect(labelFlagged(), isFalse);
    expect(find.byIcon(LpgIcons.error), findsNothing);

    formKey.currentState!.validate();
    await tester.pump();
    await tester.pump();
    expect(labelFlagged(), isTrue);
    expect(find.byIcon(LpgIcons.error), findsOneWidget);

    await tester.enterText(find.byType(TextFormField), '9876543210');
    await tester.pump();
    await tester.pump();
    expect(find.text('Required'), findsNothing);
    expect(labelFlagged(), isFalse);
    expect(find.byIcon(LpgIcons.error), findsNothing);
  });

  testWidgets('LpgStatusBadge renders its label', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const LpgStatusBadge(
          label: 'Delivered',
          severity: LpgStatusSeverity.success,
        ),
      ),
    );
    expect(find.text('Delivered'), findsOneWidget);
  });

  testWidgets('LpgListTile chevrons line up whatever the trailing content', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        Column(
          children: [
            LpgListTile(title: 'Plain', showChevron: true, onTap: () {}),
            LpgListTile(
              title: 'With a badge',
              trailing: const LpgStatusBadge(
                label: '5',
                severity: LpgStatusSeverity.danger,
              ),
              showChevron: true,
              onTap: () {},
            ),
            LpgListTile(
              title: 'With a long status',
              trailing: const LpgStatusBadge(
                label: 'Out for delivery',
                severity: LpgStatusSeverity.warning,
              ),
              showChevron: true,
              onTap: () {},
            ),
          ],
        ),
      ),
    );

    final chevrons = find.byIcon(LpgIcons.chevronRight);
    expect(chevrons, findsNWidgets(3));
    final rights = [
      for (var i = 0; i < 3; i++) tester.getTopRight(chevrons.at(i)).dx,
    ];
    expect(rights[1], rights[0]);
    expect(rights[2], rights[0]);
  });

  testWidgets('a row with no chevron can keep its space, so the trailing '
      'icons of a mixed list line up', (tester) async {
    const icon = Icon(LpgIcons.success);
    await tester.pumpWidget(
      _wrap(
        Column(
          children: [
            LpgListTile(
              title: 'Opens',
              trailing: icon,
              showChevron: true,
              onTap: () {},
            ),
            const LpgListTile(
              title: 'Does not open',
              trailing: icon,
              reserveChevronSpace: true,
            ),
          ],
        ),
      ),
    );

    final icons = find.byIcon(LpgIcons.success);
    expect(
      tester.getTopRight(icons.at(1)).dx,
      tester.getTopRight(icons.at(0)).dx,
    );
  });

  testWidgets('a grouped list keeps trailing content in line when only some '
      'rows have a chevron', (tester) async {
    const icon = Icon(LpgIcons.success);
    await tester.pumpWidget(
      _wrap(
        LpgGroupedList(
          children: [
            LpgListTile(
              title: 'Opens',
              trailing: icon,
              showChevron: true,
              onTap: () {},
            ),
            const LpgListTile(title: 'Does not open', trailing: icon),
          ],
        ),
      ),
    );
    await tester.pumpAndSettle();

    final icons = find.byIcon(LpgIcons.success);
    expect(
      tester.getTopRight(icons.at(1)).dx,
      tester.getTopRight(icons.at(0)).dx,
    );
  });

  testWidgets('LpgListTile renders title, subtitle and trailing', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        const LpgListTile(
          title: 'Order #123',
          subtitle: 'Delivered today',
          leadingIcon: LpgIcons.cylinder,
          trailing: Text('₹905.50'),
        ),
      ),
    );
    expect(find.text('Order #123'), findsOneWidget);
    expect(find.text('Delivered today'), findsOneWidget);
    expect(find.text('₹905.50'), findsOneWidget);
  });

  testWidgets('LpgEmptyState shows the action button when provided', (
    tester,
  ) async {
    var tapped = false;
    await tester.pumpWidget(
      _wrap(
        LpgEmptyState(
          message: 'No orders yet',
          actionLabel: 'Order Gas',
          onAction: () => tapped = true,
        ),
      ),
    );
    expect(find.text('No orders yet'), findsOneWidget);
    await tester.tap(find.text('Order Gas'));
    expect(tapped, isTrue);
  });

  testWidgets('LpgLoadingIndicator renders a progress indicator', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap(const LpgLoadingIndicator()));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  group('LpgButton variants', () {
    testWidgets('a button without onPressed ignores taps', (tester) async {
      await tester.pumpWidget(_wrap(const LpgButton(label: 'Go')));
      await tester.tap(find.text('Go'), warnIfMissed: false);
      // Nothing to assert beyond "no exception": there is no callback.
      expect(find.text('Go'), findsOneWidget);
    });

    testWidgets('high contrast renders native Material buttons', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.highContrast,
          home: Scaffold(
            body: Column(
              children: [
                LpgButton(label: 'Primary', onPressed: () {}),
                LpgButton(
                  label: 'Delete',
                  variant: LpgButtonVariant.destructive,
                  onPressed: () {},
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.byType(ElevatedButton), findsNWidgets(2));
    });
  });

  testWidgets('LpgCard with onTap is tappable and announces its label', (
    tester,
  ) async {
    var tapped = false;
    await tester.pumpWidget(
      _wrap(
        LpgCard(
          onTap: () => tapped = true,
          semanticLabel: 'Order 1042, delivered',
          child: const Text('Inside'),
        ),
      ),
    );
    expect(find.bySemanticsLabel('Order 1042, delivered'), findsOneWidget);
    await tester.tap(find.text('Inside'));
    await tester.pumpAndSettle();
    expect(tapped, isTrue);
  });

  testWidgets('every LpgCard variant renders in every theme', (tester) async {
    for (final variant in LpgThemeVariant.values) {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.build(variant),
          home: const Scaffold(
            body: Column(
              children: [
                LpgCard(child: Text('elevated')),
                LpgCard(variant: LpgCardVariant.outlined, child: Text('o')),
                LpgCard(
                  variant: LpgCardVariant.tonal,
                  tone: LpgTone.warning,
                  child: Text('t'),
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.text('elevated'), findsOneWidget);
    }
  });

  testWidgets('LpgDropdownField shows its label and current value', (
    tester,
  ) async {
    String? changed;
    await tester.pumpWidget(
      _wrap(
        LpgDropdownField<String>(
          label: 'Category',
          value: 'leak',
          items: const {'leak': 'Gas leak', 'late': 'Late delivery'},
          onChanged: (v) => changed = v,
        ),
      ),
    );
    expect(find.text('Category'), findsOneWidget);
    expect(find.text('Gas leak'), findsOneWidget);
    await tester.tap(find.text('Gas leak'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Late delivery').last);
    await tester.pumpAndSettle();
    expect(changed, 'late');
  });

  testWidgets('LpgErrorState shows the message and retries', (tester) async {
    var retried = false;
    await tester.pumpWidget(
      _wrap(
        LpgErrorState(message: 'Network down', onRetry: () => retried = true),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Something went wrong'), findsOneWidget);
    expect(find.text('Network down'), findsOneWidget);
    await tester.tap(find.text('Retry'));
    expect(retried, isTrue);
  });

  testWidgets('LpgSectionHeader action fires', (tester) async {
    var tapped = false;
    await tester.pumpWidget(
      _wrap(
        LpgSectionHeader(
          title: 'Recent orders',
          actionLabel: 'See all',
          onAction: () => tapped = true,
        ),
      ),
    );
    expect(find.text('Recent orders'), findsOneWidget);
    await tester.tap(find.text('See all'));
    expect(tapped, isTrue);
  });

  testWidgets('LpgStatTile and LpgQuickAction expose a combined label', (
    tester,
  ) async {
    var tapped = false;
    await tester.pumpWidget(
      _wrap(
        Row(
          children: [
            const Expanded(
              child: LpgStatTile(
                label: 'Stops left',
                value: '4',
                icon: LpgIcons.route,
              ),
            ),
            Expanded(
              child: LpgQuickAction(
                icon: LpgIcons.invoice,
                label: 'Invoices',
                onTap: () => tapped = true,
              ),
            ),
          ],
        ),
      ),
    );
    expect(find.bySemanticsLabel('Stops left: 4'), findsOneWidget);
    await tester.tap(find.bySemanticsLabel('Invoices'));
    await tester.pumpAndSettle();
    expect(tapped, isTrue);
  });

  testWidgets('LpgIconBadgeButton shows and announces the count', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        LpgIconBadgeButton(
          icon: LpgIcons.notifications,
          tooltip: 'Notifications',
          count: 3,
          onPressed: () {},
        ),
      ),
    );
    expect(find.text('3'), findsOneWidget);
    expect(find.bySemanticsLabel('Notifications, 3 unread'), findsOneWidget);
  });

  testWidgets('LpgIconBadgeButton keeps a 99+ badge on screen', (tester) async {
    await tester.pumpWidget(
      _wrap(
        Align(
          alignment: Alignment.topRight,
          child: LpgIconBadgeButton(
            icon: LpgIcons.notifications,
            tooltip: 'Alerts',
            count: 150,
            onPressed: () {},
          ),
        ),
      ),
    );
    final right = tester.getRect(find.text('99+')).right;
    expect(right, lessThanOrEqualTo(tester.view.physicalSize.width /
        tester.view.devicePixelRatio));
  });

  test('LpgAvatar.initialsOf takes first and last initials', () {
    expect(LpgAvatar.initialsOf('Asha Rao'), 'AR');
    expect(LpgAvatar.initialsOf('  asha  '), 'A');
    expect(LpgAvatar.initialsOf('Asha Devi Rao'), 'AR');
    expect(LpgAvatar.initialsOf(''), '?');
  });

  testWidgets('LpgAvatar shows only initials when there is no picture', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap(const LpgAvatar(name: 'Asha Rao')));
    expect(find.text('AR'), findsOneWidget);
    expect(find.byType(Image), findsNothing);

    await tester.pumpWidget(
      _wrap(const LpgAvatar(name: 'Asha Rao', imageUrl: '')),
    );
    expect(find.byType(Image), findsNothing);
  });

  testWidgets(
    'LpgAvatar loads the picture and keeps the initials if it fails',
    (tester) async {
      await tester.pumpWidget(
        _wrap(
          const LpgAvatar(
            name: 'Asha Rao',
            imageUrl: 'https://files.test/expired-link.png',
          ),
        ),
      );
      expect(find.byType(Image), findsOneWidget);

      // The test HTTP client refuses every request, like an expired link.
      await tester.pumpAndSettle();
      expect(find.text('AR'), findsOneWidget);
      expect(find.bySemanticsLabel('Asha Rao'), findsOneWidget);
    },
  );

  testWidgets('LpgTimeline labels each step with its state', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const LpgTimeline(
          steps: [
            LpgTimelineStep(title: 'Placed', state: LpgTimelineState.done),
            LpgTimelineStep(
              title: 'Out for delivery',
              state: LpgTimelineState.current,
            ),
            LpgTimelineStep(
              title: 'Delivered',
              state: LpgTimelineState.upcoming,
            ),
          ],
        ),
      ),
    );
    // The current-step pulse runs a fixed number of times, so this settles.
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('Placed, completed'), findsOneWidget);
    expect(
      find.bySemanticsLabel('Out for delivery, in progress'),
      findsOneWidget,
    );
    expect(find.bySemanticsLabel('Delivered, not started'), findsOneWidget);
  });

  testWidgets('LpgBanner shows title, message and action', (tester) async {
    var tapped = false;
    await tester.pumpWidget(
      _wrap(
        LpgBanner(
          title: 'KYC pending',
          message: 'Upload your ID to keep ordering.',
          tone: LpgTone.warning,
          actionLabel: 'Upload',
          onAction: () => tapped = true,
        ),
      ),
    );
    expect(find.text('KYC pending'), findsOneWidget);
    await tester.tap(find.text('Upload'));
    expect(tapped, isTrue);
  });

  testWidgets('LpgFadeSlideIn ends fully visible and in place', (tester) async {
    await tester.pumpWidget(
      _wrap(const LpgFadeSlideIn(index: 3, child: Text('Row'))),
    );
    await tester.pumpAndSettle();
    final opacity = tester.widget<Opacity>(
      find.ancestor(of: find.text('Row'), matching: find.byType(Opacity)),
    );
    expect(opacity.opacity, 1.0);
  });

  testWidgets('LpgFadeSlideIn does not animate rows past the first screenful', (
    tester,
  ) async {
    // A row built far down while a list scrolls must not animate an opacity
    // layer mid-scroll.
    await tester.pumpWidget(
      _wrap(const LpgFadeSlideIn(index: 40, child: Text('Row'))),
    );
    expect(tester.hasRunningAnimations, isFalse);
    expect(
      find.ancestor(of: find.text('Row'), matching: find.byType(Opacity)),
      findsNothing,
    );
  });

  testWidgets('LpgFadeSlideIn renders immediately under reduce-motion', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: LpgTheme.light,
        home: const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: LpgFadeSlideIn(child: Text('Row')),
        ),
      ),
    );
    expect(
      find.ancestor(of: find.text('Row'), matching: find.byType(Opacity)),
      findsNothing,
    );
  });

  testWidgets('LpgCountUp lands on the final value', (tester) async {
    await tester.pumpWidget(_wrap(const LpgCountUp(value: 42)));
    await tester.pumpAndSettle();
    expect(find.text('42'), findsOneWidget);
  });

  testWidgets('LpgSkeletonList is announced as loading', (tester) async {
    await tester.pumpWidget(
      _wrap(const SizedBox(height: 400, child: LpgSkeletonList())),
    );
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.bySemanticsLabel('Loading'), findsOneWidget);
  });

  testWidgets('LpgFeedback.confirm resolves true only on confirm', (
    tester,
  ) async {
    bool? result;
    await tester.pumpWidget(
      _wrap(
        Builder(
          builder: (context) => TextButton(
            onPressed: () async {
              result = await LpgFeedback.confirm(
                context,
                title: 'Cancel order?',
                message: 'This cannot be undone.',
                confirmLabel: 'Cancel order',
                cancelLabel: 'Keep',
                destructive: true,
              );
            },
            child: const Text('Open'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Keep'));
    await tester.pumpAndSettle();
    expect(result, isFalse);

    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel order'));
    await tester.pumpAndSettle();
    expect(result, isTrue);
  });

  testWidgets('LpgFeedback.showToast shows the message', (tester) async {
    await tester.pumpWidget(
      _wrap(
        Builder(
          builder: (context) => TextButton(
            onPressed: () => LpgFeedback.showToast(
              context,
              'Order placed',
              tone: LpgTone.success,
            ),
            child: const Text('Go'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Go'));
    await tester.pump();
    expect(find.text('Order placed'), findsOneWidget);
  });

  testWidgets(
    'LpgNavigationBar keeps labels on one line at a large font size',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          home: MediaQuery(
            data: const MediaQueryData(
              size: Size(360, 640),
              textScaler: TextScaler.linear(2),
            ),
            child: Scaffold(
              bottomNavigationBar: LpgNavigationBar(
                selectedIndex: 0,
                onDestinationSelected: (_) {},
                destinations: const [
                  LpgNavDestination(
                    icon: LpgIcons.home,
                    selectedIcon: LpgIcons.homeFilled,
                    label: 'Dashboard',
                  ),
                  LpgNavDestination(
                    icon: LpgIcons.orders,
                    selectedIcon: LpgIcons.ordersFilled,
                    label: 'Orders',
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      // The bar is the only place the scale is capped: 2x outside, at most 1.1x
      // inside, so a 10-point label never grows past 11.
      final inside = tester.element(find.text('Dashboard'));
      expect(MediaQuery.textScalerOf(inside).scale(10), closeTo(11, 0.001));
      expect(find.text('Dashboard'), findsOneWidget);
    },
  );

  testWidgets('LpgNavigationBar renders destinations with a badge', (
    tester,
  ) async {
    var selected = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: LpgTheme.light,
        home: Scaffold(
          bottomNavigationBar: LpgNavigationBar(
            selectedIndex: 0,
            onDestinationSelected: (i) => selected = i,
            destinations: const [
              LpgNavDestination(
                icon: LpgIcons.home,
                selectedIcon: LpgIcons.homeFilled,
                label: 'Home',
              ),
              LpgNavDestination(
                icon: LpgIcons.notifications,
                selectedIcon: LpgIcons.notificationsFilled,
                label: 'Alerts',
                badgeCount: 2,
              ),
            ],
          ),
        ),
      ),
    );
    expect(find.byType(LpgNavigationBar), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    await tester.tap(find.byTooltip('Alerts, 2 new'));
    expect(selected, 1);
  });

  testWidgets('LpgTextField gives the input its label as an accessible name', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(
      _wrap(const LpgTextField(label: 'Address line 1', isRequired: true)),
    );
    expect(
      tester.getSemantics(find.byType(EditableText)),
      isSemantics(label: 'Address line 1, required', isTextField: true),
    );
    // The visible label is not announced a second time.
    expect(find.bySemanticsLabel('Address line 1'), findsNothing);
    handle.dispose();
  });

  group('LpgAdaptiveShell', () {
    const destinations = [
      LpgNavDestination(
        icon: LpgIcons.home,
        selectedIcon: LpgIcons.homeFilled,
        label: 'Home',
      ),
      LpgNavDestination(
        icon: LpgIcons.orders,
        selectedIcon: LpgIcons.ordersFilled,
        label: 'Orders',
      ),
    ];

    Future<void> pumpAt(WidgetTester tester, Size size) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          home: LpgAdaptiveShell(
            destinations: destinations,
            selectedIndex: 0,
            onDestinationSelected: (_) {},
            body: const SizedBox.expand(key: Key('body')),
          ),
        ),
      );
    }

    testWidgets('uses a bottom bar on a phone', (tester) async {
      await pumpAt(tester, const Size(390, 844));
      expect(find.byType(LpgNavigationBar), findsOneWidget);
      expect(find.byType(NavigationRail), findsNothing);
      expect(tester.getSize(find.byKey(const Key('body'))).width, 390);
    });

    testWidgets('uses a rail and caps content width on a tablet', (
      tester,
    ) async {
      await pumpAt(tester, const Size(820, 1180));
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(LpgNavigationBar), findsNothing);
      expect(
        tester.getSize(find.byKey(const Key('body'))).width,
        lessThanOrEqualTo(LpgBreakpoints.contentMaxWidth),
      );
    });
  });

  group('LpgDropdownField', () {
    testWidgets('shows the placeholder when the value is not an item', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          LpgDropdownField<String>(
            value: '',
            placeholder: 'Select a cylinder type',
            items: const {'a': 'Domestic 14.2kg'},
            onChanged: (_) {},
          ),
        ),
      );
      expect(tester.takeException(), isNull);
      expect(find.text('Select a cylinder type'), findsOneWidget);
    });

    testWidgets('shows the chosen item', (tester) async {
      await tester.pumpWidget(
        _wrap(
          LpgDropdownField<String>(
            value: 'a',
            placeholder: 'Select',
            items: const {'a': 'Domestic 14.2kg'},
            onChanged: (_) {},
          ),
        ),
      );
      expect(find.text('Domestic 14.2kg'), findsOneWidget);
    });

    testWidgets('opens a sheet with every option and ticks the current one', (
      tester,
    ) async {
      String? changed = 'unchanged';
      await tester.pumpWidget(
        _wrap(
          LpgDropdownField<String>(
            label: 'From',
            value: 'bpcl',
            placeholder: 'Not sure',
            items: const {'iocl': 'Indane', 'bpcl': 'Bharatgas'},
            onChanged: (v) => changed = v,
          ),
        ),
      );

      await tester.tap(find.text('Bharatgas'));
      await tester.pumpAndSettle();
      expect(find.text('Indane'), findsOneWidget);
      expect(find.text('Not sure'), findsOneWidget);
      expect(find.byIcon(LpgIcons.check), findsOneWidget);
      expect(find.byType(TextField), findsNothing); // too short to search

      await tester.tap(find.text('Not sure'));
      await tester.pumpAndSettle();
      expect(changed, isNull); // choosing "nothing" is a real choice
    });

    testWidgets('dismissing the sheet changes nothing', (tester) async {
      var calls = 0;
      await tester.pumpWidget(
        _wrap(
          LpgDropdownField<String>(
            value: 'a',
            items: const {'a': 'One', 'b': 'Two'},
            onChanged: (_) => calls++,
          ),
        ),
      );
      await tester.tap(find.text('One'));
      await tester.pumpAndSettle();
      await tester.tapAt(const Offset(5, 5));
      await tester.pumpAndSettle();
      expect(calls, 0);
      expect(find.text('Two'), findsNothing);
    });

    testWidgets('a long list can be searched', (tester) async {
      String? changed;
      await tester.pumpWidget(
        _wrap(
          LpgDropdownField<String>(
            value: '',
            placeholder: 'Pick one',
            items: {for (var i = 1; i <= 9; i++) 'k$i': 'Godown $i'},
            onChanged: (v) => changed = v,
          ),
        ),
      );
      await tester.tap(find.text('Pick one'));
      await tester.pumpAndSettle();
      // Nothing is chosen, so there is nothing to clear: no placeholder row.
      expect(find.widgetWithText(LpgListTile, 'Pick one'), findsNothing);

      await tester.enterText(find.byType(TextField), '7');
      await tester.pumpAndSettle();
      expect(find.text('Godown 6'), findsNothing);
      await tester.tap(find.text('Godown 7'));
      await tester.pumpAndSettle();
      expect(changed, 'k7');
    });

    testWidgets('does nothing when disabled', (tester) async {
      await tester.pumpWidget(
        _wrap(
          const LpgDropdownField<String>(
            value: 'a',
            items: {'a': 'One', 'b': 'Two'},
            onChanged: null,
          ),
        ),
      );
      await tester.tap(find.text('One'));
      await tester.pumpAndSettle();
      expect(find.text('Two'), findsNothing);
    });

    testWidgets('shows a validator message under the field', (tester) async {
      final formKey = GlobalKey<FormState>();
      await tester.pumpWidget(
        _wrap(
          Form(
            key: formKey,
            child: LpgDropdownField<String>(
              value: '',
              items: const {'a': 'One'},
              validator: (v) => v == null ? 'Choose one.' : null,
              onChanged: (_) {},
            ),
          ),
        ),
      );
      formKey.currentState!.validate();
      await tester.pump();
      expect(find.text('Choose one.'), findsOneWidget);
    });
  });

  group('LpgGroupedList', () {
    testWidgets('puts every row in one card with a divider between rows', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          const LpgGroupedList(
            children: [
              LpgListTile(title: 'Order ORD1', subtitle: 'Closed'),
              LpgListTile(title: 'Order ORD2', subtitle: 'Out for delivery'),
              LpgListTile(title: 'Order ORD3', subtitle: 'Ready for dispatch'),
            ],
          ),
        ),
      );
      await tester.pump(const Duration(seconds: 2));
      expect(find.byType(LpgCard), findsOneWidget);
      expect(find.byType(LpgListTile), findsNWidgets(3));
      expect(find.byType(Divider), findsNWidgets(2));
      // Edge to edge: no inset from the card's side.
      for (final d in tester.widgetList<Divider>(find.byType(Divider))) {
        expect(d.indent, isNull);
        expect(d.endIndent, isNull);
      }
    });
  });

  group('LpgHeroCard', () {
    Future<double> contentWidth(
      WidgetTester tester, {
      required bool keepClear,
      IconData? watermark = Icons.receipt_long,
    }) async {
      await tester.pumpWidget(
        _wrap(
          LpgHeroCard(
            watermark: watermark,
            keepClearOfWatermark: keepClear,
            child: const SizedBox(
              key: Key('content'),
              width: double.infinity,
              height: 10,
            ),
          ),
        ),
      );
      return tester.getSize(find.byKey(const Key('content'))).width;
    }

    testWidgets('lets the content use the full width by default', (
      tester,
    ) async {
      final plain = await contentWidth(tester, keepClear: false);
      final noWatermark = await contentWidth(
        tester,
        keepClear: true,
        watermark: null,
      );

      expect(noWatermark, plain);
    });

    testWidgets('keeps the content out of the watermark corner when asked', (
      tester,
    ) async {
      final plain = await contentWidth(tester, keepClear: false);
      final clear = await contentWidth(tester, keepClear: true);

      expect(clear, lessThan(plain));
      // The icon reaches 80 logical pixels into the content box.
      expect(plain - clear, closeTo(80, 0.5));
    });
  });

  group('LpgMetricTile', () {
    testWidgets('reads as one label and fires onTap', (tester) async {
      var taps = 0;
      await tester.pumpWidget(
        _wrap(
          LpgMetricTile(
            label: 'Cash with drivers',
            value: '₹2,717',
            caption: '4 to review',
            icon: Icons.payments,
            tone: LpgTone.accent,
            onTap: () => taps++,
          ),
        ),
      );

      expect(
        find.bySemanticsLabel('Cash with drivers: ₹2,717, 4 to review'),
        findsOneWidget,
      );
      await tester.tap(find.text('₹2,717'));
      expect(taps, 1);
    });

    testWidgets('keeps the same content position with or without the bar', (
      tester,
    ) async {
      Future<Offset> valueTopLeft({required bool attention}) async {
        await tester.pumpWidget(
          _wrap(
            SizedBox(
              width: 200,
              child: LpgMetricTile(
                label: 'Overdue',
                value: '₹35,916',
                icon: Icons.schedule,
                attention: attention,
              ),
            ),
          ),
        );
        return tester.getTopLeft(find.text('₹35,916'));
      }

      expect(
        await valueTopLeft(attention: true),
        await valueTopLeft(attention: false),
      );
    });

    testWidgets('colours the caption only when the tile needs attention', (
      tester,
    ) async {
      Future<Color?> captionColor({required bool attention}) async {
        await tester.pumpWidget(
          _wrap(
            LpgMetricTile(
              label: 'Overdue',
              value: '4',
              caption: 'Needs review',
              icon: Icons.schedule,
              tone: LpgTone.danger,
              attention: attention,
            ),
          ),
        );
        return tester.widget<Text>(find.text('Needs review')).style?.color;
      }

      final calm = await captionColor(attention: false);
      final urgent = await captionColor(attention: true);
      expect(calm, isNot(urgent));
    });

    testWidgets('has no bar down its left edge, attention or not', (
      tester,
    ) async {
      for (final attention in [true, false]) {
        await tester.pumpWidget(
          _wrap(
            LpgMetricTile(
              label: 'Overdue',
              value: '4',
              icon: Icons.schedule,
              attention: attention,
            ),
          ),
        );

        expect(
          find.byWidgetPredicate(
            (w) => w is SizedBox && w.width == 4 && w.child is ColoredBox,
          ),
          findsNothing,
        );
      }
    });
  });

  group('LpgButton size and focus', () {
    testWidgets('large is taller than regular', (tester) async {
      Future<double> heightOf(LpgButtonSize size) async {
        await tester.pumpWidget(
          _wrap(
            Column(
              children: [LpgButton(label: 'Go', onPressed: () {}, size: size)],
            ),
          ),
        );
        return tester.getSize(find.byType(LpgButton)).height;
      }

      final regular = await heightOf(LpgButtonSize.regular);
      final large = await heightOf(LpgButtonSize.large);
      expect(large, greaterThan(regular));
      expect(large, LpgSizes.buttonHeightLarge);
    });

    testWidgets('keyboard focus draws a ring around the button', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(LpgButton(label: 'One', onPressed: () {})));
      expect(find.byKey(const ValueKey('focus-ring')), findsNothing);

      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();

      expect(find.byKey(const ValueKey('focus-ring')), findsOneWidget);
    });
  });

  group('LpgFeedback.showSheet', () {
    testWidgets('shows the title, subtitle and a Close button that dismisses', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          Builder(
            builder: (context) => TextButton(
              onPressed: () => LpgFeedback.showSheet<void>(
                context,
                title: 'Record payment',
                subtitle: 'INV-12 · ₹500 due',
                builder: (_) => const Text('body'),
              ),
              child: const Text('open'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      expect(find.text('Record payment'), findsOneWidget);
      expect(find.text('INV-12 · ₹500 due'), findsOneWidget);
      expect(find.text('body'), findsOneWidget);

      await tester.tap(find.byTooltip('Close'));
      await tester.pumpAndSettle();
      expect(find.text('body'), findsNothing);
    });
  });

  group('LpgActionRow', () {
    testWidgets('right aligns the buttons with the standard gap', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          SizedBox(
            // The test font is wide, so give the buttons room to share a line.
            width: 700,
            child: LpgActionRow(
              children: [
                LpgButton(label: 'Dispute', onPressed: () {}),
                LpgButton(label: 'Accept & Verify', onPressed: () {}),
              ],
            ),
          ),
        ),
      );

      final first = tester.getRect(find.byType(LpgButton).first);
      final last = tester.getRect(find.byType(LpgButton).last);
      final rowRight = tester.getTopRight(find.byType(LpgActionRow)).dx;
      expect(last.right, rowRight, reason: 'the main action is at the edge');
      expect(last.left - first.right, LpgActionRow.gap);
      expect(first.top, last.top);
    });

    testWidgets('wraps onto a second line, still right aligned, when full', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          SizedBox(
            width: 200,
            child: LpgActionRow(
              children: [
                LpgButton(label: 'Dispute the amount', onPressed: () {}),
                LpgButton(label: 'Accept & Verify', onPressed: () {}),
              ],
            ),
          ),
        ),
      );

      final first = tester.getRect(find.byType(LpgButton).first);
      final last = tester.getRect(find.byType(LpgButton).last);
      expect(last.top, greaterThan(first.bottom));
      expect(last.right, tester.getTopRight(find.byType(LpgActionRow)).dx);
      expect(first.right, last.right);
    });

    // The visible button, not the widget around it: a button's own box is
    // what has to be an equal share.
    final shown = find.descendant(
      of: find.byType(LpgButton),
      matching: find.byType(Material),
    );

    Future<void> pumpEqual(WidgetTester tester, {double textScale = 1.0}) =>
        tester.pumpWidget(
          _wrap(
            MediaQuery(
              data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
              child: SizedBox(
                width: 400,
                child: LpgActionRow.equal(
                  children: [
                    LpgButton(label: 'Dispute', onPressed: () {}),
                    LpgButton(label: 'Accept & Verify', onPressed: () {}),
                  ],
                ),
              ),
            ),
          ),
        );

    testWidgets('equal: the buttons share the row in equal halves', (
      tester,
    ) async {
      await pumpEqual(tester);

      final first = tester.getRect(shown.first);
      final last = tester.getRect(shown.last);
      expect(first.width, last.width);
      expect(first.left, tester.getTopLeft(find.byType(LpgActionRow)).dx);
      expect(last.right, tester.getTopRight(find.byType(LpgActionRow)).dx);
      expect(last.left - first.right, LpgActionRow.gap);
      expect(first.top, last.top);
    });

    testWidgets('equal: at large text the buttons stack, each full width', (
      tester,
    ) async {
      await pumpEqual(tester, textScale: 2.0);

      final first = tester.getRect(shown.first);
      final last = tester.getRect(shown.last);
      expect(first.width, 400);
      expect(last.width, 400);
      expect(last.top - first.bottom, LpgActionRow.gap);
    });
  });

  group('LpgSheetLayout and LpgSheetActions', () {
    testWidgets('the footer stays on screen while a long body scrolls', (
      tester,
    ) async {
      var saved = 0;
      tester.view.physicalSize = const Size(800, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        _wrap(
          Builder(
            builder: (context) => TextButton(
              onPressed: () => LpgFeedback.showSheet<void>(
                context,
                title: 'Long form',
                builder: (_) => LpgSheetLayout(
                  body: Column(
                    children: [
                      for (var i = 0; i < 40; i++)
                        SizedBox(height: 48, child: Text('row $i')),
                    ],
                  ),
                  footer: LpgSheetActions(
                    primaryLabel: 'Save',
                    onPrimary: () => saved++,
                    error: 'Enter the amount.',
                  ),
                ),
              ),
              child: const Text('open'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      // Far down the list is off screen, the footer is not.
      expect(tester.getTopLeft(find.text('row 39')).dy, greaterThan(900));
      expect(
        tester.getTopLeft(find.text('Enter the amount.')).dy,
        lessThan(900),
      );
      await tester.tap(find.text('Save'));
      expect(saved, 1);
    });

    testWidgets('a loading primary action cannot be pressed again', (
      tester,
    ) async {
      var pressed = 0;
      await tester.pumpWidget(
        _wrap(
          LpgSheetActions(
            primaryLabel: 'Save',
            onPrimary: () => pressed++,
            isLoading: true,
            secondaryLabel: 'Cancel',
            onSecondary: () => pressed++,
          ),
        ),
      );

      await tester.tap(find.byType(LpgButton).first, warnIfMissed: false);
      await tester.tap(find.text('Cancel'), warnIfMissed: false);
      expect(pressed, 0);
    });

    testWidgets('a second decision can be loading; both buttons then wait', (
      tester,
    ) async {
      var pressed = 0;
      await tester.pumpWidget(
        _wrap(
          LpgSheetActions(
            primaryLabel: 'Accept',
            onPrimary: () => pressed++,
            secondaryLabel: 'Reject',
            secondaryVariant: LpgButtonVariant.secondary,
            isSecondaryLoading: true,
            onSecondary: () => pressed++,
          ),
        ),
      );

      final buttons = tester.widgetList<LpgButton>(find.byType(LpgButton));
      expect(buttons.last.variant, LpgButtonVariant.secondary);
      expect(buttons.last.isLoading, isTrue);
      expect(buttons.first.isLoading, isFalse);
      expect(buttons.first.onPressed, isNull);

      await tester.tap(find.text('Accept'), warnIfMissed: false);
      expect(pressed, 0);
    });

    testWidgets(
      'a second action is a quiet text button unless told otherwise',
      (tester) async {
        await tester.pumpWidget(
          _wrap(
            LpgSheetActions(
              primaryLabel: 'Save',
              onPrimary: () {},
              secondaryLabel: 'Cancel',
              onSecondary: () {},
            ),
          ),
        );

        expect(
          tester.widgetList<LpgButton>(find.byType(LpgButton)).last.variant,
          LpgButtonVariant.text,
        );
      },
    );
  });

  group('LpgHaptics', () {
    testWidgets('a stepper tap ticks once and still reports the change', (
      tester,
    ) async {
      final calls = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          if (call.method == 'HapticFeedback.vibrate') {
            calls.add(call.arguments as String);
          }
          return null;
        },
      );
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform,
          null,
        ),
      );
      int? changed;
      await tester.pumpWidget(
        _wrap(LpgQuantityStepper(value: 1, onChanged: (v) => changed = v)),
      );

      await tester.tap(find.byTooltip('Increase'));
      await tester.pump();

      expect(changed, 2);
      expect(calls, ['HapticFeedbackType.selectionClick']);
    });

    test('names map to distinct strengths', () async {
      final calls = <String>[];
      TestWidgetsFlutterBinding.ensureInitialized();
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, (call) async {
            if (call.method == 'HapticFeedback.vibrate') {
              calls.add(call.arguments as String);
            }
            return null;
          });
      await LpgHaptics.selection();
      await LpgHaptics.success();
      await LpgHaptics.warning();
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null);

      expect(calls, [
        'HapticFeedbackType.selectionClick',
        'HapticFeedbackType.mediumImpact',
        'HapticFeedbackType.heavyImpact',
      ]);
    });
  });

  group('LpgActionCard', () {
    testWidgets('reads as one button and fires onTap', (tester) async {
      var taps = 0;
      await tester.pumpWidget(
        _wrap(
          LpgActionCard(
            icon: Icons.local_shipping,
            title: 'On its way',
            message: 'ORD000060 is out for delivery',
            actionLabel: 'Track',
            onTap: () => taps++,
          ),
        ),
      );

      expect(
        find.bySemanticsLabel('On its way. ORD000060 is out for delivery'),
        findsOneWidget,
      );
      expect(find.text('Track'), findsOneWidget);
      await tester.tap(find.text('On its way'));
      expect(taps, 1);
    });
  });

  group('LpgHeroStats', () {
    testWidgets('shows each figure with its label under a hero card', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          LpgHeroCard(
            child: LpgHeroStats(
              stats: [
                LpgHeroStat(value: '12', label: 'Delivered'),
                LpgHeroStat(value: '1', label: 'Failed'),
                LpgHeroStat(value: '3', label: 'To approve'),
              ],
            ),
          ),
        ),
      );

      for (final text in [
        '12',
        'Delivered',
        '1',
        'Failed',
        '3',
        'To approve',
      ]) {
        expect(find.text(text), findsOneWidget);
      }
      expect(
        tester.getSemantics(find.text('12')).label,
        contains('Delivered: 12'),
      );
      expect(tester.takeException(), isNull);
    });
  });

  group('LpgSplash', () {
    testWidgets('shows the name, tagline and badge once it has played', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          home: LpgSplash(
            logo: MemoryImage(_transparentPixel),
            title: 'LPG Agency Admin',
            tagline: 'Operations & agency control',
            badge: 'Admin Console',
          ),
        ),
      );
      await tester.pump(const Duration(seconds: 2));
      expect(find.text('LPG Agency Admin'), findsOneWidget);
      expect(find.text('Operations & agency control'), findsOneWidget);
      expect(find.text('Admin Console'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('draws the finished frame at once under reduce-motion', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: child!,
          ),
          home: LpgSplash(
            logo: MemoryImage(_transparentPixel),
            title: 'LPG Agency',
            tagline: 'Your gas, delivered safely.',
          ),
        ),
      );
      await tester.pump();
      expect(find.text('LPG Agency'), findsOneWidget);
      expect(tester.hasRunningAnimations, isFalse);
    });
  });

  group('shared chips, tag, FAB and segmented control', () {
    testWidgets('a filter row scrolls sideways and "All" can be a null key', (
      tester,
    ) async {
      String? picked = 'unset';
      await tester.pumpWidget(
        _wrap(
          LpgChoiceChips<String?>.filterRow(
            options: const {
              null: 'All',
              'Open': 'Open',
              'Resolved': 'Resolved',
            },
            selected: null,
            onSelected: (v) => picked = v,
          ),
        ),
      );

      // "All" (the null key) is the selected chip.
      final all = tester.widget<ChoiceChip>(
        find.widgetWithText(ChoiceChip, 'All'),
      );
      expect(all.selected, isTrue);
      expect(find.byType(SingleChildScrollView), findsOneWidget);

      await tester.tap(find.text('Resolved'));
      expect(picked, 'Resolved');
      // Tapping the chip that is already selected changes nothing.
      picked = 'unset';
      await tester.tap(find.text('All'));
      expect(picked, 'unset');
    });

    testWidgets('a filter tag shows its label and removes itself', (
      tester,
    ) async {
      var removed = 0;
      await tester.pumpWidget(
        _wrap(
          LpgFilterTag(
            icon: LpgIcons.user,
            label: 'Ramesh Traders',
            removeTooltip: 'Show every customer',
            onRemove: () => removed++,
          ),
        ),
      );

      expect(find.text('Ramesh Traders'), findsOneWidget);
      await tester.tap(find.byTooltip('Show every customer'));
      expect(removed, 1);
    });

    testWidgets('the FAB is extended with a label, or small with a tooltip', (
      tester,
    ) async {
      var pressed = 0;
      await tester.pumpWidget(
        _wrap(
          Column(
            children: [
              LpgFab.extended(
                heroTag: 'a',
                icon: LpgIcons.add,
                label: 'New order',
                onPressed: () => pressed++,
              ),
              LpgFab.small(
                heroTag: 'b',
                icon: LpgIcons.recenter,
                tooltip: 'Recenter map',
                onPressed: () => pressed += 10,
              ),
            ],
          ),
        ),
      );

      await tester.tap(find.text('New order'));
      await tester.tap(find.byTooltip('Recenter map'));
      expect(pressed, 11);
    });

    testWidgets('the segmented control reports a change once, not a re-tap', (
      tester,
    ) async {
      final changes = <String>[];
      await tester.pumpWidget(
        _wrap(
          LpgSegmentedControl<String>(
            options: const {'otp': 'Phone OTP', 'email': 'Email'},
            icons: const {'otp': LpgIcons.smartphone},
            selected: 'otp',
            onSelected: changes.add,
          ),
        ),
      );

      await tester.tap(find.text('Phone OTP'));
      await tester.tap(find.text('Email'));
      expect(changes, ['email']);
    });
  });

  group('LpgSplashOffline', () {
    Widget splash({required VoidCallback onRetry, bool retrying = false}) =>
        MaterialApp(
          theme: LpgTheme.light,
          localizationsDelegates: lpgLocalizationsDelegates,
          home: LpgSplash(
            logo: MemoryImage(_transparentPixel),
            title: 'LPG Agency',
            tagline: 'Your gas, delivered safely.',
            footer: LpgSplashOffline(onRetry: onRetry, retrying: retrying),
          ),
        );

    testWidgets('says it cannot reach the server, and Retry fires', (
      tester,
    ) async {
      var retried = 0;
      await tester.pumpWidget(splash(onRetry: () => retried++));
      await tester.pump(const Duration(seconds: 2));

      expect(find.text("Can't reach the server"), findsOneWidget);
      expect(find.textContaining('sign-in is safe'), findsOneWidget);
      await tester.tap(find.text('Retry'));
      expect(retried, 1);
      expect(tester.takeException(), isNull);
    });

    testWidgets('while an attempt runs the button says so and is off', (
      tester,
    ) async {
      var retried = 0;
      await tester.pumpWidget(splash(onRetry: () => retried++, retrying: true));
      await tester.pump(const Duration(seconds: 2));

      expect(find.text('Trying…'), findsOneWidget);
      await tester.tap(find.text('Trying…'), warnIfMissed: false);
      expect(retried, 0);
    });

    testWidgets('fits a small phone at 2x text without overflow', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(
            size: Size(320, 568),
            textScaler: TextScaler.linear(2),
          ),
          child: splash(onRetry: () {}),
        ),
      );
      await tester.pump(const Duration(seconds: 2));
      expect(tester.takeException(), isNull);
    });
  });

  group('LpgProgressBar', () {
    testWidgets('the filled part stands out from the track by 3:1 or more', (
      tester,
    ) async {
      for (final v in LpgThemeVariant.values) {
        final c = LpgTheme.colorsFor(v);
        final track = c.tint(c.textSecondary, 0.25, over: c.card);

        expect(
          LpgBackdropLook.contrast(c.actionPrimary, track),
          greaterThanOrEqualTo(3),
          reason: '$v',
        );
      }
    });

    testWidgets('reports its progress to a screen reader', (tester) async {
      final semantics = tester.ensureSemantics();
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.build(LpgThemeVariant.light),
          home: const Scaffold(
            body: LpgProgressBar(value: 0.5, semanticsLabel: 'Trip progress'),
          ),
        ),
      );

      expect(find.bySemanticsLabel('Trip progress'), findsOneWidget);
      semantics.dispose();
    });
  });

  group('section headings', () {
    testWidgets('a header is sentence case, normal weight, main colour', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(const LpgSectionHeader(title: 'Godown and papers')),
      );

      // Shown exactly as written: no capitals added.
      final text = tester.widget<Text>(find.text('Godown and papers'));
      final colors = LpgTheme.colorsFor(LpgThemeVariant.light);
      expect(text.style?.color, colors.textPrimary);
      expect(text.style?.fontWeight, FontWeight.w400);
    });

    testWidgets('a header is still announced as a heading, once', (
      tester,
    ) async {
      final semantics = tester.ensureSemantics();
      await tester.pumpWidget(_wrap(const LpgSectionHeader(title: 'Recent')));

      expect(
        tester.getSemantics(find.text('Recent')),
        matchesSemantics(label: 'Recent', isHeader: true),
      );
      semantics.dispose();
    });

    testWidgets('spacing is automatic: none above the first child of a list, '
        'a gap above the rest', (tester) async {
      await tester.pumpWidget(
        _wrap(
          ListView(
            children: const [
              LpgSectionHeader(title: 'First'),
              SizedBox(height: 40),
              LpgSectionHeader(title: 'Second'),
            ],
          ),
        ),
      );

      final first = tester.getTopLeft(find.text('First')).dy;
      final second = tester.getTopLeft(find.text('Second')).dy;
      final firstBox = tester
          .getTopLeft(find.byType(LpgSectionHeader).first)
          .dy;
      final secondBox = tester
          .getTopLeft(find.byType(LpgSectionHeader).last)
          .dy;
      // The first heading's text starts at the top of its own box...
      expect(first - firstBox, 0);
      // ...and the later one is pushed down by the section gap.
      expect(second - secondBox, LpgSpacing.lg);
    });

    testWidgets(
      'a heading inside a column is not the first thing on the page',
      (tester) async {
        await tester.pumpWidget(
          _wrap(
            ListView(
              children: const [
                Column(children: [LpgSectionHeader(title: 'Nested')]),
              ],
            ),
          ),
        );

        final text = tester.getTopLeft(find.text('Nested')).dy;
        final box = tester.getTopLeft(find.byType(LpgSectionHeader)).dy;
        expect(text - box, LpgSpacing.lg);
      },
    );
  });
}

/// A 1x1 transparent PNG, so the splash has a real image to decode.
final _transparentPixel = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
);
