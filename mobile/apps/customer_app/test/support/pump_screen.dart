import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Pumps [app] on a tall logical surface and settles.
///
/// Several customer-app screens put their content in a non-scrolling
/// `Column` or a lazy `ListView`; on the default 800x600 test window that
/// overflows (a layout exception) or leaves lower sections unbuilt. A tall
/// surface lays every section out so `find.text` sees the whole screen.
/// The view is reset after the test via [addTearDown].
Future<void> pumpScreen(WidgetTester tester, Widget app) async {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(app);
  await tester.pumpAndSettle();
}
