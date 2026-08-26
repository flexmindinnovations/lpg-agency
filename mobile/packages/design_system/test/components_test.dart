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
      await tester.pumpWidget(
        _wrap(LpgButton(label: 'Go', isLoading: true, onPressed: () {})),
      );
      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);
    });
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
