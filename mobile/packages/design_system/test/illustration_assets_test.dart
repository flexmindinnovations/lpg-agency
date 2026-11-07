import 'dart:io';

import 'package:design_system/design_system.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// The picture files are the contract between the artists and the tile: they
/// may only use the four palette colours (so every tone and theme works) and
/// nothing that is transparent (the design system has no transparency).
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final dir = Directory('assets/illustrations');
  final files = [
    for (final f in dir.listSync())
      if (f is File && f.path.endsWith('.svg')) f,
  ];

  String name(File f) => f.uri.pathSegments.last.replaceAll('.svg', '');

  test('every picture in the enum has a file and every file is used', () {
    final named = {for (final a in LpgIllustration.values) a.fileName};
    expect({for (final f in files) name(f)}, named);
  });

  test('assetPath points inside the package', () {
    for (final a in LpgIllustration.values) {
      expect(File(a.assetPath).existsSync(), isTrue, reason: a.assetPath);
    }
  });

  final allowed = {
    for (final c in LpgIllustrationPalette.all)
      '#${(c.toARGB32() & 0xFFFFFF).toRadixString(16).padLeft(6, '0')}',
  };

  for (final f in files) {
    group(name(f), () {
      final svg = f.readAsStringSync();

      test('is a 100 x 100 picture', () {
        expect(svg, contains('viewBox="0 0 100 100"'));
      });

      test('uses only the four palette colours', () {
        final colours = RegExp(
          r'(?:fill|stroke)="(#[0-9A-Fa-f]{3,8}|[a-z]+)"',
        ).allMatches(svg).map((m) => m.group(1)!.toLowerCase());
        for (final c in colours) {
          expect(
            c == 'none' || allowed.contains(c),
            isTrue,
            reason: '$c is not a palette colour',
          );
        }
      });

      test('has nothing transparent, blurred or textual', () {
        for (final banned in const [
          'opacity',
          'gradient',
          'filter',
          '<text',
          '<image',
          '<mask',
        ]) {
          expect(svg.contains(banned), isFalse, reason: 'contains $banned');
        }
      });
    });
  }

  test('the files are declared as package assets', () async {
    for (final a in LpgIllustration.values) {
      final data = await rootBundle.load(
        'packages/design_system/${a.assetPath}',
      );
      expect(data.lengthInBytes, greaterThan(0));
    }
  });
}
