import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import 'gallery_entries.dart';

/// All gallery groups on one scrollable page, each under its name.
class ComponentGallery extends StatelessWidget {
  const ComponentGallery({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Component gallery')),
      body: ListView(
        padding: LpgSpacing.page,
        children: [
          for (final entry in galleryEntries) ...[
            Padding(
              padding: const EdgeInsets.only(
                top: LpgSpacing.lg,
                bottom: LpgSpacing.sm,
              ),
              child: Text(
                entry.name.replaceAll('_', ' '),
                style: context.lpgText.titleMedium,
              ),
            ),
            entry.builder(context),
          ],
        ],
      ),
    );
  }
}
