import 'package:flutter/material.dart';

import '../theme.dart';

/// A themed, centered loading spinner — the default `CircularProgress
/// Indicator()` picks up Material's ambient primary colour, not this
/// app's actual action colour per theme variant, so every loading screen
/// needs this instead.
class LpgLoadingIndicator extends StatelessWidget {
  const LpgLoadingIndicator({super.key, this.size = 32});

  final double size;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    return Center(
      child: SizedBox(
        width: size,
        height: size,
        child: CircularProgressIndicator(
          strokeWidth: 3,
          valueColor: AlwaysStoppedAnimation<Color>(colors.actionPrimary),
        ),
      ),
    );
  }
}
