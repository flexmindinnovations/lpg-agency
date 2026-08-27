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
    // The label renders uppercase (a deliberate LpgTextField style choice).
    expect(find.text('PHONE'), findsOneWidget);
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
          leadingIcon: Icons.local_gas_station_outlined,
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
}
