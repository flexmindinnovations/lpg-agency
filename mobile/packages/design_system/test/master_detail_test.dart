import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester tester, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      theme: LpgTheme.light,
      home: Scaffold(
        body: LpgMasterDetail(
          emptyMessage: 'Pick one.',
          masterBuilder: (context, md) => ListView(
            children: [
              for (final id in const ['a', 'b'])
                ListTile(
                  title: Text('Row $id'),
                  onTap: () {
                    if (!md.open(id)) {
                      // A phone would navigate here.
                    }
                  },
                ),
            ],
          ),
          detailBuilder: (context, id) => Text('Detail $id'),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('a tablet shows the list beside the chosen detail', (
    tester,
  ) async {
    await _pump(tester, const Size(1280, 800));
    expect(find.text('Pick one.'), findsOneWidget);

    await tester.tap(find.text('Row b'));
    await tester.pump();
    expect(find.text('Detail b'), findsOneWidget);
    expect(find.text('Row a'), findsOneWidget);
  });

  testWidgets('a phone shows only the list and leaves navigation to it', (
    tester,
  ) async {
    await _pump(tester, const Size(400, 800));
    expect(find.text('Pick one.'), findsNothing);

    await tester.tap(find.text('Row a'));
    await tester.pump();
    expect(find.text('Detail a'), findsNothing);
  });
}
