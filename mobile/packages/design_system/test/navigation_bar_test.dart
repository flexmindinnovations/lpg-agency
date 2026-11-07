import 'dart:ui' as ui;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _destinations = [
  LpgNavDestination(
    icon: LpgIcons.home,
    selectedIcon: LpgIcons.homeFilled,
    label: 'Dashboard',
  ),
  LpgNavDestination(
    icon: LpgIcons.orders,
    selectedIcon: LpgIcons.ordersFilled,
    label: 'Orders',
    badgeCount: 3,
  ),
  LpgNavDestination(
    icon: LpgIcons.truck,
    selectedIcon: LpgIcons.truck,
    label: 'Dispatch',
  ),
  LpgNavDestination(
    icon: LpgIcons.more,
    selectedIcon: LpgIcons.more,
    label: 'More',
  ),
];

/// Sizes the test window like a phone, so the bar has the width it claims.
void _phone(WidgetTester tester, [double width = 390]) {
  tester.view.physicalSize = Size(width, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
}

Widget _bar({
  required int selected,
  ValueChanged<int>? onSelected,
  bool reduceMotion = false,
  double width = 390,
}) => MaterialApp(
  theme: LpgTheme.light,
  home: MediaQuery(
    data: MediaQueryData(
      size: Size(width, 700),
      disableAnimations: reduceMotion,
    ),
    child: Scaffold(
      bottomNavigationBar: LpgNavigationBar(
        destinations: _destinations,
        selectedIndex: selected,
        onDestinationSelected: onSelected ?? (_) {},
      ),
    ),
  ),
);

/// How wide a tab's label is on screen: zero while it is hidden.
double _labelWidth(WidgetTester tester, String label) => tester
    .getSize(
      find
          .ancestor(of: find.text(label), matching: find.byType(ClipRect))
          .first,
    )
    .width;

/// The width of a tab's whole cell.
double _cellWidth(WidgetTester tester, String label) => tester
    .getSize(
      find
          .ancestor(
            of: find.byTooltip(label),
            matching: find.byType(Positioned),
          )
          .first,
    )
    .width;

void main() {
  testWidgets('only the active tab shows its label', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_bar(selected: 0));

    expect(_labelWidth(tester, 'Dashboard'), greaterThan(40));
    expect(_labelWidth(tester, 'Orders'), 0);
    expect(_labelWidth(tester, 'Dispatch'), 0);
    expect(_labelWidth(tester, 'More'), 0);
  });

  testWidgets('the active tab is wider and the row always fills the bar', (
    tester,
  ) async {
    _phone(tester);
    await tester.pumpWidget(_bar(selected: 1));

    final cells = [
      for (final d in _destinations)
        _cellWidth(
          tester,
          d.badgeCount > 0 ? '${d.label}, ${d.badgeCount} new' : d.label,
        ),
    ];
    expect(cells[1], greaterThan(cells[0]));
    expect(cells[0], cells[2]);
    // Never below a tap target, and together exactly the bar's inner width.
    for (final w in cells) {
      expect(w, greaterThanOrEqualTo(LpgSizes.touchTarget));
    }
    expect(
      cells.reduce((a, b) => a + b),
      closeTo(390 - 2 * LpgSpacing.smd, 0.5),
    );
  });

  testWidgets('switching tabs animates the label across, then settles', (
    tester,
  ) async {
    _phone(tester);
    await tester.pumpWidget(_bar(selected: 0));
    final full = _labelWidth(tester, 'Dashboard');
    await tester.pumpWidget(_bar(selected: 1));
    await tester.pump(const Duration(milliseconds: 150));

    // Part way: the old label is shrinking while the new one grows.
    final leaving = _labelWidth(tester, 'Dashboard');
    final arriving = _labelWidth(tester, 'Orders');
    expect(leaving, inExclusiveRange(0, full));
    expect(arriving, inExclusiveRange(0, full));
    expect(tester.hasRunningAnimations, isTrue);

    await tester.pumpAndSettle();
    expect(_labelWidth(tester, 'Dashboard'), 0);
    expect(_labelWidth(tester, 'Orders'), greaterThan(20));
    expect(tester.hasRunningAnimations, isFalse);
  });

  testWidgets('there is one pill and it slides to the new tab', (tester) async {
    _phone(tester);
    final pill = find.byWidgetPredicate(
      (w) =>
          w is DecoratedBox &&
          w.decoration is ShapeDecoration &&
          (w.decoration as ShapeDecoration).shape is StadiumBorder &&
          (w.decoration as ShapeDecoration).color ==
              LpgTheme.colorsFor(LpgThemeVariant.light).actionPrimaryContainer,
    );
    Rect cell(String label) => tester.getRect(
      find
          .ancestor(
            of: find.byTooltip(label),
            matching: find.byType(Positioned),
          )
          .first,
    );

    await tester.pumpWidget(_bar(selected: 0));
    expect(pill, findsOneWidget);
    final start = tester.getRect(pill);
    expect(start.left, closeTo(cell('Dashboard').left, 0.5));

    await tester.pumpWidget(_bar(selected: 2));
    await tester.pump(const Duration(milliseconds: 150));
    // On the way: still one pill, between where it was and where it is going.
    expect(pill, findsOneWidget);
    final middle = tester.getRect(pill);
    expect(middle.left, greaterThan(start.left));

    await tester.pumpAndSettle();
    final end = tester.getRect(pill);
    expect(middle.left, lessThan(end.left));
    // At rest it sits exactly under the active tab.
    expect(end.left, closeTo(cell('Dispatch').left, 0.5));
    expect(end.width, closeTo(cell('Dispatch').width, 0.5));
  });

  testWidgets('under reduce-motion the change is instant', (tester) async {
    _phone(tester);
    await tester.pumpWidget(_bar(selected: 0, reduceMotion: true));
    await tester.pumpWidget(_bar(selected: 3, reduceMotion: true));
    // One frame, no time passing: already in its final state.
    await tester.pump();

    expect(_labelWidth(tester, 'Dashboard'), 0);
    expect(_labelWidth(tester, 'More'), greaterThan(20));
  });

  testWidgets('tapping a tab reports its index, wherever on the cell', (
    tester,
  ) async {
    _phone(tester);
    int? picked;
    await tester.pumpWidget(_bar(selected: 0, onSelected: (i) => picked = i));

    await tester.tap(find.byTooltip('Dispatch'));
    expect(picked, 2);
    await tester.tap(find.byTooltip('Orders, 3 new'));
    expect(picked, 1);
  });

  testWidgets('each tab is a named button and the active one is selected', (
    tester,
  ) async {
    _phone(tester);
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(_bar(selected: 1));

    final orders = tester.getSemantics(find.byTooltip('Orders, 3 new'));
    expect(orders.label, 'Orders, 3 new');
    expect(orders.flagsCollection.isButton, isTrue);
    expect(orders.flagsCollection.isSelected, ui.Tristate.isTrue);
    expect(orders.getSemanticsData().hasAction(ui.SemanticsAction.tap), isTrue);

    final dispatch = tester.getSemantics(find.byTooltip('Dispatch'));
    expect(dispatch.flagsCollection.isSelected, ui.Tristate.isFalse);
    handle.dispose();
  });

  testWidgets('a long label shrinks to fit instead of crowding the others', (
    tester,
  ) async {
    _phone(tester, 300);
    await tester.pumpWidget(_bar(selected: 0, width: 300));

    for (final d in _destinations) {
      final name = d.badgeCount > 0
          ? '${d.label}, ${d.badgeCount} new'
          : d.label;
      expect(
        _cellWidth(tester, name),
        greaterThanOrEqualTo(LpgSizes.touchTarget),
      );
    }
    expect(tester.takeException(), isNull);
  });
}
