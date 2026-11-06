import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// The grain tile shared by the page and by glass surfaces, decoded once for
/// the whole app. Internal: not exported from `design_system.dart`.
abstract final class LpgGrain {
  static const asset = 'packages/design_system/assets/textures/paper_grain.png';

  /// `null` until decoded (or for good if the asset cannot be read, which is
  /// fine: the page and glass then simply have no grain).
  static final ValueNotifier<ui.Image?> image = ValueNotifier(null);
  static bool _loading = false;

  /// The tile is drawn at this scale, so a speck is about one device pixel on
  /// a typical phone.
  static const scale = 0.5;

  static Future<void> ensureLoaded() async {
    if (image.value != null || _loading) return;
    _loading = true;
    try {
      final data = await rootBundle.load(asset);
      final codec = await ui.instantiateImageCodec(
        data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
      );
      image.value = (await codec.getNextFrame()).image;
    } on Object {
      // No grain is fine.
    } finally {
      _loading = false;
    }
  }

  /// Fills [rect] with the tiled grain at [strength] (0 to 1).
  static void paint(Canvas canvas, Rect rect, ui.Image tile, double strength) {
    if (strength <= 0) return;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = ImageShader(
          tile,
          TileMode.repeated,
          TileMode.repeated,
          Matrix4.diagonal3Values(scale, scale, 1).storage,
          filterQuality: FilterQuality.medium,
        )
        ..color = Color.fromRGBO(255, 255, 255, strength),
    );
  }
}
