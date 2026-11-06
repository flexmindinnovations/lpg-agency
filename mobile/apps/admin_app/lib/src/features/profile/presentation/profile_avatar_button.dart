import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../providers.dart';
import '../data/profile_photo.dart';
import '../data/profile_provider.dart';

enum _PhotoChoice { camera, gallery, remove }

/// The signed-in admin's own picture: tap it to take a photo, choose one from
/// the gallery, or remove the current one.
class ProfileAvatarButton extends ConsumerStatefulWidget {
  const ProfileAvatarButton({
    super.key,
    required this.name,
    required this.imageUrl,
  });

  final String name;

  /// The current picture's link, or `null` when there is none.
  final String? imageUrl;

  @override
  ConsumerState<ProfileAvatarButton> createState() =>
      _ProfileAvatarButtonState();
}

class _ProfileAvatarButtonState extends ConsumerState<ProfileAvatarButton> {
  bool _busy = false;

  bool get _hasPicture => (widget.imageUrl ?? '').isNotEmpty;

  Future<void> _choose() async {
    final choice = await LpgFeedback.showSheet<_PhotoChoice>(
      context,
      title: 'Profile picture',
      builder: (sheetContext) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgListTile(
            leadingIcon: LpgIcons.camera,
            title: 'Take photo',
            onTap: () => Navigator.of(sheetContext).pop(_PhotoChoice.camera),
          ),
          LpgListTile(
            leadingIcon: LpgIcons.gallery,
            title: 'Choose from gallery',
            onTap: () => Navigator.of(sheetContext).pop(_PhotoChoice.gallery),
          ),
          if (_hasPicture)
            LpgListTile(
              leadingIcon: LpgIcons.delete,
              title: 'Remove photo',
              onTap: () => Navigator.of(sheetContext).pop(_PhotoChoice.remove),
            ),
        ],
      ),
    );
    if (choice == null || !mounted) return;
    switch (choice) {
      case _PhotoChoice.camera:
        await _pick(ImageSource.camera);
      case _PhotoChoice.gallery:
        await _pick(ImageSource.gallery);
      case _PhotoChoice.remove:
        await _run(
          ref.read(authApiProvider).removeMyAvatar,
          done: 'Profile picture removed.',
        );
    }
  }

  Future<void> _pick(ImageSource source) async {
    final XFile? file;
    try {
      // A phone photo is far bigger than a small circle needs: shrink it
      // before it is sent.
      file = await ref
          .read(profilePhotoPickerProvider)
          .pickImage(
            source: source,
            maxWidth: 1024,
            maxHeight: 1024,
            imageQuality: 85,
          );
    } catch (_) {
      _tell('Could not open the camera or gallery.', LpgTone.danger);
      return;
    }
    if (file == null || !mounted) return;
    final bytes = await file.readAsBytes();
    final kind = pictureKind(bytes);
    if (kind == null) {
      _tell('Choose a JPEG, PNG, WebP or HEIC picture.', LpgTone.danger);
      return;
    }
    await _run(
      () => ref
          .read(authApiProvider)
          .setMyAvatar(
            bytes: bytes,
            filename: 'profile.${kind.extension}',
            contentType: kind.contentType,
          ),
      done: 'Profile picture updated.',
    );
  }

  Future<void> _run(
    Future<Result<MyProfile>> Function() action, {
    required String done,
  }) async {
    setState(() => _busy = true);
    final result = await action();
    if (!mounted) return;
    setState(() => _busy = false);
    switch (result) {
      case Success<MyProfile>():
        ref.invalidate(adminProfileProvider);
        _tell(done, LpgTone.success);
      case FailureResult<MyProfile>(:final failure):
        _tell(failure.message, LpgTone.danger);
    }
  }

  void _tell(String message, LpgTone tone) {
    if (!mounted) return;
    LpgFeedback.showToast(context, message, tone: tone);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    const size = LpgSizes.avatarLg;
    const badge = 24.0;
    return Semantics(
      button: true,
      label: 'Change profile picture',
      excludeSemantics: true,
      child: SizedBox(
        width: size,
        height: size,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            LpgAvatar(name: widget.name, size: size, imageUrl: widget.imageUrl),
            if (_busy)
              Positioned.fill(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: colors.surfaceRaised,
                  ),
                  child: const LpgLoadingIndicator(size: 24),
                ),
              ),
            Positioned(
              right: -LpgSpacing.xs,
              bottom: -LpgSpacing.xs,
              child: Container(
                width: badge,
                height: badge,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: colors.actionPrimaryContainer,
                  border: Border.all(color: colors.card, width: 2),
                ),
                child: Icon(
                  LpgIcons.camera,
                  size: 12,
                  color: colors.onActionPrimaryContainer,
                ),
              ),
            ),
            Positioned.fill(
              child: Material(
                type: MaterialType.transparency,
                child: InkWell(
                  customBorder: const CircleBorder(),
                  onTap: _busy ? null : _choose,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
