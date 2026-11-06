import 'package:design_system/design_system.dart';
import 'package:design_system/gallery.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/gallery_harness.dart';

/// How much of a picture may differ before the test fails. Text and edges are
/// anti-aliased a hair differently on Windows, macOS and Linux, so an exact
/// match would fail on a machine that did not make the file. A moved, resized
/// or recoloured component differs by far more than this.
const _tolerance = 0.005;

/// Compares like the default file comparator, but forgives a difference of
/// up to [tolerance] (a fraction of all pixels).
class _TolerantComparator extends LocalFileComparator {
  _TolerantComparator(super.testFile, {required this.tolerance});

  final double tolerance;

  @override
  Future<bool> compare(Uint8List imageBytes, Uri golden) async {
    final result = await GoldenFileComparator.compareLists(
      imageBytes,
      await getGoldenBytes(golden),
    );
    if (result.passed || result.diffPercent <= tolerance) return true;
    final error = await generateFailureOutput(result, golden, basedir);
    throw FlutterError(error);
  }
}

/// A picture of every gallery group in every theme. When a component changes
/// on purpose, regenerate with
/// `flutter test test/gallery_golden_test.dart --update-goldens`
/// and review the changed images in the pull request.
void main() {
  setUpAll(loadGalleryFonts);

  final previous = goldenFileComparator;
  final base = (previous as LocalFileComparator).basedir;
  goldenFileComparator = _TolerantComparator(
    base.resolve('gallery_golden_test.dart'),
    tolerance: _tolerance,
  );
  tearDownAll(() => goldenFileComparator = previous);

  for (final variant in LpgThemeVariant.values) {
    for (final entry in galleryEntries) {
      testWidgets('${entry.name} in ${variant.name}', (tester) async {
        await pumpGalleryEntry(tester, entry, variant);

        await expectLater(
          find.byKey(galleryBoundaryKey),
          matchesGoldenFile('goldens/${entry.name}_${variant.name}.png'),
        );
      });
    }
  }
}
