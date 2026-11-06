import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:device_identity/device_identity.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _strings = DeviceStrings(
  nameTitle: 'Name this phone',
  nameIntro: 'Give it a name your agency will know.',
  nameFieldLabel: 'Phone name',
  nameFieldHint: 'For example: Van 2',
  nameWhy: 'We tell your agency which phone this is.',
  nameContinue: 'Continue',
  waitingTitle: 'Waiting for approval',
  waitingMessage: 'Your agency has to approve this phone.',
  waitingPhoneLabel: 'This phone',
  waitingCheckAgain: 'Check again',
  waitingStillWaiting: 'Not approved yet.',
  waitingSignOut: 'Sign out',
  blockedTitle: 'This phone is blocked',
  blockedMessage: 'Please contact your agency.',
  blockedTryAgain: 'Try again',
);

class _Api extends DeviceApi {
  _Api() : super(Dio());

  int calls = 0;

  @override
  Future<Result<DeviceStatusReport>> me() async {
    calls++;
    return const Success(
      DeviceStatusReport(control: 'enforce', status: 'pending', allowed: false),
    );
  }
}

Widget _app(Widget child) => MaterialApp(theme: LpgTheme.light, home: child);

void main() {
  group('NameThisPhoneScreen', () {
    testWidgets('starts with the suggested name and sends the trimmed name', (
      tester,
    ) async {
      String? sent;
      await tester.pumpWidget(
        _app(
          NameThisPhoneScreen(
            strings: _strings,
            suggestedName: 'Redmi 12',
            onSubmit: (name) async => sent = name,
          ),
        ),
      );

      expect(find.text('Name this phone'), findsOneWidget);
      expect(
        find.text('We tell your agency which phone this is.'),
        findsOneWidget,
      );
      await tester.enterText(find.byType(TextField), '  Van 2 phone ');
      await tester.pump();
      await tester.tap(find.text('Continue'));
      await tester.pump();

      expect(sent, 'Van 2 phone');
    });

    testWidgets('cannot continue with an empty name', (tester) async {
      var sent = false;
      await tester.pumpWidget(
        _app(
          NameThisPhoneScreen(
            strings: _strings,
            suggestedName: 'Redmi 12',
            onSubmit: (_) async => sent = true,
          ),
        ),
      );

      await tester.enterText(find.byType(TextField), '   ');
      await tester.pump();
      await tester.tap(find.text('Continue'));
      await tester.pump();

      expect(sent, isFalse);
    });
  });

  group('WaitingForApprovalScreen', () {
    testWidgets('shows the phone name and asks again on a timer', (
      tester,
    ) async {
      final api = _Api();
      final controller = DeviceAccessController(api: api);
      await tester.pumpWidget(
        _app(
          WaitingForApprovalScreen(
            strings: _strings,
            phoneName: 'Van 2 phone',
            controller: controller,
            onSignOut: () {},
            pollInterval: const Duration(seconds: 15),
          ),
        ),
      );

      expect(find.text('Waiting for approval'), findsOneWidget);
      expect(find.text('Van 2 phone'), findsOneWidget);
      expect(api.calls, 0);

      await tester.pump(const Duration(seconds: 16));
      expect(api.calls, 1);
      await tester.pump(const Duration(seconds: 15));
      expect(api.calls, 2);

      // Leaving the screen stops the polling.
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(minutes: 1));
      expect(api.calls, 2);
    });

    testWidgets('"Check again" asks now and says when still waiting', (
      tester,
    ) async {
      final api = _Api();
      final controller = DeviceAccessController(api: api)
        ..reportRefusal('DEVICE_PENDING');
      await tester.pumpWidget(
        _app(
          WaitingForApprovalScreen(
            strings: _strings,
            phoneName: 'Van 2 phone',
            controller: controller,
            onSignOut: () {},
          ),
        ),
      );
      expect(find.text('Not approved yet.'), findsNothing);

      await tester.tap(find.text('Check again'));
      await tester.pump();
      await tester.pump();

      expect(api.calls, 1);
      expect(find.text('Not approved yet.'), findsOneWidget);
    });

    testWidgets('signing out is always possible', (tester) async {
      var signedOut = false;
      await tester.pumpWidget(
        _app(
          WaitingForApprovalScreen(
            strings: _strings,
            phoneName: 'Van 2 phone',
            controller: DeviceAccessController(api: _Api()),
            onSignOut: () => signedOut = true,
          ),
        ),
      );

      await tester.tap(find.text('Sign out'));

      expect(signedOut, isTrue);
    });
  });

  group('PhoneBlockedScreen', () {
    testWidgets('tells the user to contact the agency and can try again', (
      tester,
    ) async {
      var tried = false;
      await tester.pumpWidget(
        _app(
          PhoneBlockedScreen(strings: _strings, onTryAgain: () => tried = true),
        ),
      );

      expect(find.text('This phone is blocked'), findsOneWidget);
      expect(find.text('Please contact your agency.'), findsOneWidget);
      await tester.tap(find.text('Try again'));
      expect(tried, isTrue);
    });

    testWidgets('shows the saved-work line only when the app has one', (
      tester,
    ) async {
      const withQueue = DeviceStrings(
        nameTitle: 'a',
        nameIntro: 'a',
        nameFieldLabel: 'a',
        nameFieldHint: 'a',
        nameWhy: 'a',
        nameContinue: 'a',
        waitingTitle: 'a',
        waitingMessage: 'a',
        waitingPhoneLabel: 'a',
        waitingCheckAgain: 'a',
        waitingStillWaiting: 'a',
        waitingSignOut: 'a',
        blockedTitle: 'Blocked',
        blockedMessage: 'Contact your agency.',
        blockedTryAgain: 'Try again',
        blockedKeptWork: 'Your deliveries are saved on this phone.',
      );
      await tester.pumpWidget(
        _app(PhoneBlockedScreen(strings: withQueue, onTryAgain: () {})),
      );
      expect(
        find.text('Your deliveries are saved on this phone.'),
        findsOneWidget,
      );

      await tester.pumpWidget(
        _app(PhoneBlockedScreen(strings: _strings, onTryAgain: () {})),
      );
      expect(find.textContaining('saved on this phone'), findsNothing);
    });
  });
}
