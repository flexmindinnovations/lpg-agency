import 'package:customer_app/src/features/profile/presentation/widgets/address_form_fields.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maps/maps.dart';
import 'package:maps/maps_testing.dart';

void main() {
  testWidgets('city, state and a 6-digit pincode are required (CA-16)', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final formKey = GlobalKey<FormState>();
    TextEditingController c([String text = '']) =>
        TextEditingController(text: text);
    final pincode = c('5600');
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          mapTileProviderProvider.overrideWithValue(FakeTileProvider()),
        ],
        child: MaterialApp(
          theme: LpgTheme.light,
          home: Scaffold(
            body: SingleChildScrollView(
              child: Form(
                key: formKey,
                child: AddressFormFields(
                  addressType: 'delivery',
                  onAddressTypeChanged: (_) {},
                  line1: c('12 MG Road'),
                  line2: c(),
                  landmark: c(),
                  area: c(),
                  city: c(),
                  state: c(),
                  pincode: pincode,
                  pinnedLocation: null,
                  onPinnedLocationChanged: (_) {},
                ),
              ),
            ),
          ),
        ),
      ),
    );

    expect(formKey.currentState!.validate(), isFalse);
    await tester.pump();
    expect(find.text('Enter the city.'), findsOneWidget);
    expect(find.text('Enter the state.'), findsOneWidget);
    expect(find.text('Enter the 6-digit pincode.'), findsOneWidget);

    pincode.text = '560001';
    expect(formKey.currentState!.validate(), isFalse);
    await tester.pump();
    expect(find.text('Enter the 6-digit pincode.'), findsNothing);
  });
}
