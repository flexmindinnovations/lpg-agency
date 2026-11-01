import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _TwoActions extends StatefulWidget {
  const _TwoActions({required this.save, required this.send});

  final Future<void> Function() save;
  final Future<void> Function() send;

  @override
  State<_TwoActions> createState() => _TwoActionsState();
}

class _TwoActionsState extends State<_TwoActions>
    with LpgBusyActions<_TwoActions> {
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        LpgButton(
          label: 'Save',
          isLoading: isBusy('save'),
          onPressed: anyBusy ? null : () => runBusy('save', widget.save),
        ),
        LpgButton(
          label: 'Send',
          isLoading: isBusy('send'),
          onPressed: anyBusy ? null : () => runBusy('send', widget.send),
        ),
      ],
    );
  }
}

Widget _wrap(Widget child) => MaterialApp(
  theme: LpgTheme.light,
  home: Scaffold(body: Center(child: child)),
);

void main() {
  testWidgets('only the tapped button spins and the other is disabled', (
    tester,
  ) async {
    final gate = Completer<void>();
    var sends = 0;
    await tester.pumpWidget(
      _wrap(_TwoActions(save: () => gate.future, send: () async => sends++)),
    );

    await tester.tap(find.text('Save'));
    await tester.pump();

    // One spinner (on Save), and Send is inert while Save runs.
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Save'), findsNothing);
    await tester.tap(find.text('Send'));
    await tester.pump();
    expect(sends, 0);

    gate.complete();
    await tester.pumpAndSettle();
    expect(find.byType(CircularProgressIndicator), findsNothing);
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();
    expect(sends, 1);
  });
}
