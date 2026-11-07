import 'package:admin_app/src/login_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('the sign-in screen opens on email and password', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(theme: LpgTheme.light, home: const LoginScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Sign In with Email'), findsOneWidget);
    expect(find.text('Send Sign-In Code'), findsNothing);
  });

  testWidgets('the phone code is one tap away', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(theme: LpgTheme.light, home: const LoginScreen()),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Phone OTP'));
    await tester.pump();

    expect(find.text('Send Sign-In Code'), findsOneWidget);
  });
}
