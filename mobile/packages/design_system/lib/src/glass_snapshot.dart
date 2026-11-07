import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

/// Marks the part of the app a frosted sheet is frosted from: everything the
/// navigator shows. `ThemeEngine.builder` puts one around every app.
///
/// A live backdrop blur redraws the whole blurred area every frame the sheet
/// moves, which is what makes a sheet stutter. This does the blur **once**
/// instead: when a sheet is about to open, [LpgGlassSnapshot.capture] takes a
/// small picture of the screen, blurs it, and the sheet draws that still
/// picture behind its fill. Opening and closing then move one image, which is
/// as cheap as a sheet without glass.
class LpgGlassSource extends StatefulWidget {
  const LpgGlassSource({super.key, required this.child});

  final Widget child;

  @override
  State<LpgGlassSource> createState() => _LpgGlassSourceState();
}

class _LpgGlassSourceState extends State<LpgGlassSource> {
  final _boundary = GlobalKey();

  @override
  Widget build(BuildContext context) => _GlassSourceScope(
    boundary: _boundary,
    child: RepaintBoundary(key: _boundary, child: widget.child),
  );
}

class _GlassSourceScope extends InheritedWidget {
  const _GlassSourceScope({required this.boundary, required super.child});

  final GlobalKey boundary;

  @override
  bool updateShouldNotify(_GlassSourceScope old) => boundary != old.boundary;
}

/// The blurred picture of the screen behind a sheet.
abstract final class LpgGlassSnapshot {
  /// How much of the screen's resolution the picture keeps. It is going to be
  /// blurred, so little detail is needed, and a small picture is quick to take.
  static const pixelRatio = 0.2;

  /// The blur, in the picture's own pixels (about 27 logical pixels).
  static const sigma = 5.5;

  /// A blurred picture of what [context]'s app shows now, or `null` when there
  /// is nothing to take it from (no [LpgGlassSource] above, or the picture
  /// could not be made). The caller owns the image and disposes it.
  static Future<ui.Image?> capture(BuildContext context) async {
    final scope = context
        .getInheritedWidgetOfExactType<_GlassSourceScope>()
        ?.boundary;
    final object = scope?.currentContext?.findRenderObject();
    if (object is! RenderRepaintBoundary || object.debugNeedsPaint) return null;
    ui.Image? small;
    try {
      small = await object.toImage(pixelRatio: pixelRatio);
      final w = small.width;
      final h = small.height;
      final recorder = ui.PictureRecorder();
      Canvas(recorder)
        ..saveLayer(
          Rect.fromLTWH(0, 0, w.toDouble(), h.toDouble()),
          Paint()
            ..imageFilter = ui.ImageFilter.blur(
              sigmaX: sigma,
              sigmaY: sigma,
              tileMode: TileMode.clamp,
            ),
        )
        ..drawImage(small, Offset.zero, Paint())
        ..restore();
      return await recorder.endRecording().toImage(w, h);
    } on Object {
      return null;
    } finally {
      small?.dispose();
    }
  }
}

/// Draws a [LpgGlassSnapshot] to fill a sheet: the part of the screen the sheet
/// covers when it rests (the bottom of the picture), stretched to the sheet's
/// size. The sheet slides over the screen but the picture does not follow it;
/// blurred this much the difference cannot be seen.
class LpgSnapshotPainter extends CustomPainter {
  const LpgSnapshotPainter(this.image, {required this.screenHeight});

  final ui.Image image;

  /// Height of the screen the picture was taken of, in logical pixels.
  final double screenHeight;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty || screenHeight <= 0) return;
    final share = (size.height / screenHeight).clamp(0.05, 1.0);
    final h = image.height.toDouble();
    canvas.drawImageRect(
      image,
      Rect.fromLTWH(0, h * (1 - share), image.width.toDouble(), h * share),
      Offset.zero & size,
      Paint()..filterQuality = FilterQuality.low,
    );
  }

  @override
  bool shouldRepaint(LpgSnapshotPainter old) =>
      old.image != image || old.screenHeight != screenHeight;
}
