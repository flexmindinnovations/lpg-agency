import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
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
    await tester.tap(find.text('Try again'));
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

  test('LpgAvatar.initialsOf takes first and last initials', () {
    expect(LpgAvatar.initialsOf('Asha Rao'), 'AR');
    expect(LpgAvatar.initialsOf('  asha  '), 'A');
    expect(LpgAvatar.initialsOf('Asha Devi Rao'), 'AR');
    expect(LpgAvatar.initialsOf(''), '?');
  });

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
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    await tester.tap(find.text('Alerts'));
    expect(selected, 1);
  });
}
