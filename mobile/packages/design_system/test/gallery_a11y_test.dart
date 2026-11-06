import 'package:design_system/design_system.dart';
import 'package:design_system/gallery.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/gallery_harness.dart';

/// Contrast shortfalls we know about and have deliberately not fixed here.
/// The light theme's info blue (#2563EB) on its tint (#E5ECFD) is 4.37:1
/// against the 4.5:1 target. The tokens are shared with the web dashboard, so
/// the change is decided in story 10.1 (see `token-audit.md` in
/// `planning/features/61-mobile-ui-revamp/`). Remove the entry when fixed:
/// the test below then checks that group again.
const _knownContrastGaps = {'status_and_banners / light'};

/// Groups drawn on the textured page. Flutter's contrast guideline samples the
/// picture around each text and cannot tell a speckled background from text,
/// so it reports nonsense there. Their contrast is held instead by
/// `backdrop_test.dart`, which checks the worst pixel of the page analytically.
const _texturedGroups = {'page_backdrop', 'glass_surfaces'};

/// Every gallery group, in every theme, at normal and very large text:
/// nothing overflows, every tap target is big enough and named, and text has
/// enough contrast.
void main() {
  setUpAll(loadGalleryFonts);

  for (final variant in LpgThemeVariant.values) {
    for (final scale in const [1.0, 2.0]) {
      for (final entry in galleryEntries) {
        testWidgets('${entry.name} / ${variant.name} / text ${scale}x', (
          tester,
        ) async {
          final semantics = tester.ensureSemantics();
          await pumpGalleryEntry(tester, entry, variant, textScale: scale);

          // An overflow or layout error is reported as a test failure by
          // the framework; check the guidelines on top of that.
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          if (!_knownContrastGaps.contains('${entry.name} / ${variant.name}') &&
              !_texturedGroups.contains(entry.name)) {
            await expectLater(tester, meetsGuideline(textContrastGuideline));
          }
          semantics.dispose();
        });
      }
    }
  }
}
