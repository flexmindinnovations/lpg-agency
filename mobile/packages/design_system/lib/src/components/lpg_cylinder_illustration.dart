import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import '../tone.dart';

/// Known LPG Cylinder Sizes across Domestic, Commercial and Industrial.
enum LpgCylinderSize {
  /// 14.2 kg Domestic Cylinder (Standard red/deep blue)
  domestic14kg,

  /// 19.0 kg Commercial Cylinder (Gas Blue)
  commercial19kg,

  /// 47.5 kg Industrial Cylinder (Heavy Duty)
  industrial47kg,

  /// 5.0 kg Compact / Portable Cylinder
  compact5kg,
}

/// Cylinder fill/inspection status.
enum LpgCylinderState { full, empty, defective, leaking }

/// A proprietary, custom-painted vector illustration component for LPG Cylinders.
///
/// Draws proportional cylinder geometry including the protective steel collar,
/// dual lifting handles, brass valve stem, tare weight markings, and a visual
/// status ring. High contrast mode falls back to crisp high-contrast outlines.
class LpgCylinderIllustration extends StatelessWidget {
  const LpgCylinderIllustration({
    super.key,
    this.size = LpgCylinderSize.domestic14kg,
    this.state = LpgCylinderState.full,
    this.height = 64.0,
    this.showBadge = true,
  });

  final LpgCylinderSize size;
  final LpgCylinderState state;
  final double height;
  final bool showBadge;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final aspect = switch (size) {
      LpgCylinderSize.compact5kg => 0.65,
      LpgCylinderSize.domestic14kg => 0.58,
      LpgCylinderSize.commercial19kg => 0.46,
      LpgCylinderSize.industrial47kg => 0.38,
    };
    final width = height * aspect;

    final baseColor = switch (size) {
      LpgCylinderSize.domestic14kg => const Color(0xFFC8322B), // Domestic Red
      LpgCylinderSize.commercial19kg => colors.actionPrimary, // Enterprise Gas Blue
      LpgCylinderSize.industrial47kg => const Color(0xFF334155), // Slate Heavy Duty
      LpgCylinderSize.compact5kg => colors.accent, // Flame Orange
    };

    final statusColor = switch (state) {
      LpgCylinderState.full => colors.statusSuccess,
      LpgCylinderState.empty => colors.statusWarning,
      LpgCylinderState.defective || LpgCylinderState.leaking => colors.statusDanger,
    };

    final statusLabel = switch (state) {
      LpgCylinderState.full => 'Full',
      LpgCylinderState.empty => 'Empty',
      LpgCylinderState.defective => 'Defective',
      LpgCylinderState.leaking => 'Leaking',
    };

    final sizeLabel = switch (size) {
      LpgCylinderSize.domestic14kg => '14.2 kg',
      LpgCylinderSize.commercial19kg => '19.0 kg',
      LpgCylinderSize.industrial47kg => '47.5 kg',
      LpgCylinderSize.compact5kg => '5.0 kg',
    };

    return Semantics(
      label: 'LPG Cylinder $sizeLabel, $statusLabel',
      excludeSemantics: true,
      child: SizedBox(
        width: width,
        height: height,
        child: Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            CustomPaint(
              size: Size(width, height),
              painter: _CylinderPainter(
                cylinderColor: colors.isHighContrast ? colors.textPrimary : baseColor,
                borderColor: colors.isHighContrast ? colors.borderStrong : baseColor.withValues(alpha: 0.3),
                isHighContrast: colors.isHighContrast,
                state: state,
              ),
            ),
            if (showBadge)
              Positioned(
                right: -2,
                bottom: -2,
                child: Container(
                  width: 14,
                  height: 14,
                  decoration: BoxDecoration(
                    color: statusColor,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: colors.card,
                      width: 2,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CylinderPainter extends CustomPainter {
  _CylinderPainter({
    required this.cylinderColor,
    required this.borderColor,
    required this.isHighContrast,
    required this.state,
  });

  final Color cylinderColor;
  final Color borderColor;
  final bool isHighContrast;
  final LpgCylinderState state;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    final paintBody = Paint()
      ..color = cylinderColor
      ..style = isHighContrast ? PaintingStyle.stroke : PaintingStyle.fill
      ..strokeWidth = isHighContrast ? 2.0 : 0.0;

    final paintValve = Paint()
      ..color = const Color(0xFFD97706) // Brass Valve
      ..style = PaintingStyle.fill;

    final paintCollar = Paint()
      ..color = isHighContrast
          ? cylinderColor
          : Color.alphaBlend(Colors.black.withValues(alpha: 0.2), cylinderColor)
      ..style = isHighContrast ? PaintingStyle.stroke : PaintingStyle.fill
      ..strokeWidth = isHighContrast ? 1.5 : 0.0;

    final paintHighlight = Paint()
      ..color = Colors.white.withValues(alpha: 0.25)
      ..style = PaintingStyle.stroke
      ..strokeWidth = w * 0.08
      ..strokeCap = StrokeCap.round;

    // 1. Valve Stem (Top centre)
    final valveWidth = w * 0.22;
    final valveHeight = h * 0.10;
    final valveRect = RRect.fromRectAndRadius(
      Rect.fromLTWH((w - valveWidth) / 2, 0, valveWidth, valveHeight),
      const Radius.circular(2),
    );
    canvas.drawRRect(valveRect, paintValve);

    // 2. Protective Collar Ring
    final collarTop = h * 0.08;
    final collarHeight = h * 0.16;
    final collarWidth = w * 0.70;
    final collarRect = RRect.fromRectAndRadius(
      Rect.fromLTWH((w - collarWidth) / 2, collarTop, collarWidth, collarHeight),
      const Radius.circular(4),
    );
    canvas.drawRRect(collarRect, paintCollar);

    // 3. Main Tank Body
    final bodyTop = h * 0.22;
    final bodyHeight = h * 0.70;
    final bodyRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(0, bodyTop, w, bodyHeight),
      Radius.circular(w * 0.35),
    );
    canvas.drawRRect(bodyRect, paintBody);

    // 4. Glossy Highlight Reflection (Left curve)
    if (!isHighContrast) {
      final path = Path()
        ..moveTo(w * 0.20, bodyTop + (bodyHeight * 0.15))
        ..lineTo(w * 0.20, bodyTop + (bodyHeight * 0.80));
      canvas.drawPath(path, paintHighlight);
    }

    // 5. Foot Ring Base
    final baseTop = h * 0.90;
    final baseHeight = h * 0.10;
    final baseWidth = w * 0.85;
    final baseRect = RRect.fromRectAndRadius(
      Rect.fromLTWH((w - baseWidth) / 2, baseTop, baseWidth, baseHeight),
      const Radius.circular(3),
    );
    canvas.drawRRect(baseRect, paintCollar);
  }

  @override
  bool shouldRepaint(covariant _CylinderPainter oldDelegate) {
    return oldDelegate.cylinderColor != cylinderColor ||
        oldDelegate.isHighContrast != isHighContrast ||
        oldDelegate.state != state;
  }
}
