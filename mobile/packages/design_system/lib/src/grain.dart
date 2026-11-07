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

  /// The same grain, softened once into mist (see [_soften]): the page lays it
  /// under the sharp grain so the paper looks hazy rather than only speckled.
  /// `null` until made.
  static final ValueNotifier<ui.Image?> haze = ValueNotifier(null);

  /// The haze is drawn at this scale, so each cloud is larger than a speck.
  static const hazeScale = 1.0;

  /// How far the grain is blurred, in tile pixels.
  static const _hazeSigma = 3.0;

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
      final tile = (await codec.getNextFrame()).image;
      image.value = tile;
      haze.value = await _soften(tile);
    } on Object {
      // No grain is fine.
    } finally {
      _loading = false;
    }
  }

  /// [tile] blurred once, still seamless. The tile is laid 3 by 3 so the blur
  /// wraps round its edges, blurred as one picture and cropped back to the
  /// middle. Done once at start-up: nothing is blurred while the app runs.
  static Future<ui.Image> _soften(ui.Image tile) async {
    final w = tile.width;
    final h = tile.height;
    final big = ui.PictureRecorder();
    final bigCanvas = Canvas(big)
      ..saveLayer(
        Rect.fromLTWH(0, 0, w * 3.0, h * 3.0),
        Paint()
          ..imageFilter = ui.ImageFilter.blur(
            sigmaX: _hazeSigma,
            sigmaY: _hazeSigma,
            tileMode: TileMode.clamp,
          ),
      );
    for (var x = 0; x < 3; x++) {
      for (var y = 0; y < 3; y++) {
        bigCanvas.drawImage(
          tile,
          Offset(x * w.toDouble(), y * h.toDouble()),
          Paint(),
        );
      }
    }
    bigCanvas.restore();
    final wide = await big.endRecording().toImage(w * 3, h * 3);

    final crop = ui.PictureRecorder();
    Canvas(crop).drawImageRect(
      wide,
      Rect.fromLTWH(w.toDouble(), h.toDouble(), w.toDouble(), h.toDouble()),
      Rect.fromLTWH(0, 0, w.toDouble(), h.toDouble()),
      Paint(),
    );
    final softened = await crop.endRecording().toImage(w, h);
    wide.dispose();
    return softened;
  }

  /// Fills [rect] with the softened grain at [strength] (0 to 1).
  static void paintHaze(
    Canvas canvas,
    Rect rect,
    ui.Image tile,
    double strength,
  ) {
    if (strength <= 0) return;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = ImageShader(
          tile,
          TileMode.repeated,
          TileMode.repeated,
          Matrix4.diagonal3Values(hazeScale, hazeScale, 1).storage,
          filterQuality: FilterQuality.medium,
        )
        ..color = Color.fromRGBO(255, 255, 255, strength),
    );
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
