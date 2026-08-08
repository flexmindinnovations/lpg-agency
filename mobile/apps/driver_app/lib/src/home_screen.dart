import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// Placeholder shell screen. Replaced when the first feature ships.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;

    return Scaffold(
      appBar: AppBar(title: const Text('LPG Agency')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Repository foundation',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'The app shell, theme and routing are in place. '
              'Business features have not been built yet.',
              style: TextStyle(color: colors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
