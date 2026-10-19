import 'package:flutter/material.dart';

import '../theme.dart';

/// A themed, centred loading spinner, for loads with no predictable layout
/// (a submit in flight, a map tile). Lists and cards use [LpgSkeletonList] /
/// [LpgShimmer] instead, so the screen keeps its shape while loading.
class LpgLoadingIndicator extends StatelessWidget {
  const LpgLoadingIndicator({super.key, this.size = 32});

  final double size;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Center(
      child: SizedBox(
        width: size,
        height: size,
        child: CircularProgressIndicator(
          strokeWidth: 3,
          strokeCap: StrokeCap.round,
          valueColor: AlwaysStoppedAnimation<Color>(colors.actionPrimary),
          semanticsLabel: 'Loading',
        ),
      ),
    );
  }
}
