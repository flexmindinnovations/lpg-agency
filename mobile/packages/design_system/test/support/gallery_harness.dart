import 'package:design_system/design_system.dart';
import 'package:design_system/gallery.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// Loads Inter and the icon font, which `flutter test` does not do by itself.
/// Without them every letter is a solid block and every icon an empty square,
/// so neither the pictures nor the text-size checks would mean anything.
Future<void> loadGalleryFonts() async {
  Future<void> load(String family, List<String> assets) async {
    final loader = FontLoader(family);
    for (final asset in assets) {
      loader.addFont(rootBundle.load(asset));
    }
    await loader.load();
  }

  await load('packages/design_system/Inter', [
    for (final w in const [
      'Regular',
      'Medium',
      'SemiBold',
      'Bold',
      'ExtraBold',
    ])
      'fonts/inter/Inter-$w.ttf',
  ]);
  await load('packages/lucide_icons_flutter/Lucide', [
    'packages/lucide_icons_flutter/assets/lucide.ttf',
  ]);
}

/// The width the gallery is rendered at: a common phone.
const galleryWidth = 390.0;

/// The key of the box the golden tests photograph.
const galleryBoundaryKey = ValueKey('gallery-boundary');

/// Pumps one gallery group in [variant] at [textScale], with animations off
/// so skeletons, pulses and entrances are in their finished, still state.
Future<void> pumpGalleryEntry(
  WidgetTester tester,
  GalleryEntry entry,
  LpgThemeVariant variant, {
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = const Size(galleryWidth, 3000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: LpgTheme.build(variant, reduceMotion: true),
      home: MediaQuery(
        data: MediaQueryData(
          size: const Size(galleryWidth, 3000),
          disableAnimations: true,
          textScaler: TextScaler.linear(textScale),
        ),
        child: Scaffold(
          body: SingleChildScrollView(
            child: RepaintBoundary(
              key: galleryBoundaryKey,
              child: ColoredBox(
                color: LpgTheme.colorsFor(variant).canvas,
                child: Padding(
                  padding: LpgSpacing.page,
                  child: Builder(builder: entry.builder),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await settleAssets(tester);
  // Not pumpAndSettle: a loading spinner never settles.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 600));
}

/// Lets SVG illustrations finish loading. They are read and parsed off the
/// fake clock, so a plain `pump` never completes them; give the real clock a
/// moment, then pump so they are painted.
Future<void> settleAssets(WidgetTester tester) async {
  await tester.runAsync(
    () => Future<void>.delayed(const Duration(milliseconds: 300)),
  );
  await tester.pump();
}
