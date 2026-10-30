import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../providers.dart';

/// A scan of a driving licence or RC: take or pick a photo, stage it
/// (`POST /documents/attachments`) and ask for the OCR head start. The form
/// owns what to do with both through [onUploaded] and [onRecognized].
class DocumentPhotoField extends ConsumerStatefulWidget {
  const DocumentPhotoField({
    super.key,
    required this.label,
    required this.onUploaded,
    this.docKind,
    this.onRecognized,
    this.errorText,
  });

  final String label;

  /// `driving_licence` or `vehicle_rc` to read the photo for a head start;
  /// `null` for any other document, which is just stored.
  final String? docKind;

  /// The staged blob ref, or null when the photo was removed or failed.
  final ValueChanged<String?> onUploaded;
  final ValueChanged<RecognizedComplianceDocument>? onRecognized;
  final String? errorText;

  @override
  ConsumerState<DocumentPhotoField> createState() => _DocumentPhotoFieldState();
}

class _DocumentPhotoFieldState extends ConsumerState<DocumentPhotoField> {
  final _picker = ImagePicker();
  var _uploading = false;
  var _hasPhoto = false;
  String? _fileName;
  String? _error;
  String? _hint;

  Future<void> _pick(ImageSource source) async {
    final XFile? file;
    try {
      file = await _picker.pickImage(source: source, imageQuality: 85);
    } catch (_) {
      setState(() => _error = 'Could not open the camera or gallery.');
      return;
    }
    if (file == null) return;
    final bytes = await file.readAsBytes();
    setState(() {
      _uploading = true;
      _error = null;
      _hint = null;
      _hasPhoto = false;
      _fileName = file!.name;
    });
    widget.onUploaded(null);

    final api = ref.read(fleetApiProvider);
    final uploaded = await api.uploadDocument(
      bytes: bytes,
      filename: file.name,
    );
    if (!mounted) return;
    switch (uploaded) {
      case FailureResult<String>(:final failure):
        setState(() {
          _uploading = false;
          _error = 'Could not upload the photo: ${failure.message}';
        });
        return;
      case Success<String>(:final value):
        setState(() {
          _uploading = false;
          _hasPhoto = true;
        });
        widget.onUploaded(value);
        final docKind = widget.docKind;
        if (docKind == null) return;
        final recognized = await api.recognizeDocument(value, docKind);
        if (!mounted) return;
        // Reading the photo is a nice-to-have; a failure just means the
        // details are typed in.
        if (recognized case Success<RecognizedComplianceDocument>(
          :final value,
        )) {
          widget.onRecognized?.call(value);
          setState(() {
            _hint = value.confidence >= 0.5
                ? 'Filled in from the photo. Please check the details.'
                : "Couldn't read the photo clearly. Please fill the details in.";
          });
        }
    }
  }

  Future<void> _choose() => LpgFeedback.showSheet<void>(
    context,
    title: 'Add a photo',
    builder: (sheetContext) => Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        LpgListTile(
          leadingIcon: LpgIcons.camera,
          title: 'Take photo',
          onTap: () {
            Navigator.of(sheetContext).pop();
            _pick(ImageSource.camera);
          },
        ),
        LpgListTile(
          leadingIcon: LpgIcons.gallery,
          title: 'Choose from gallery',
          onTap: () {
            Navigator.of(sheetContext).pop();
            _pick(ImageSource.gallery);
          },
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final error = _error ?? widget.errorText;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgFieldLabel(widget.label, isRequired: true),
        LpgCard(
          variant: _hasPhoto ? LpgCardVariant.outlined : LpgCardVariant.tonal,
          onTap: _uploading ? null : _choose,
          child: Row(
            children: [
              LpgIconBox(
                icon: _hasPhoto ? LpgIcons.success : LpgIcons.addPhoto,
              ),
              const SizedBox(width: LpgSpacing.md),
              Expanded(
                child: Text(
                  _uploading
                      ? 'Uploading…'
                      : _hasPhoto
                      ? '${_fileName ?? 'Photo'} · tap to change'
                      : 'Tap to add a photo',
                  style: text.titleSmall,
                ),
              ),
              if (_uploading) const LpgLoadingIndicator(size: 20),
            ],
          ),
        ),
        if (error != null) ...[
          const SizedBox(height: LpgSpacing.xs),
          Text(
            error,
            style: text.bodySmall?.copyWith(color: colors.statusDanger),
          ),
        ],
        if (_hint != null) ...[
          const SizedBox(height: LpgSpacing.sm),
          LpgBanner(
            tone: LpgTone.info,
            icon: LpgIcons.sparkle,
            message: _hint!,
          ),
        ],
      ],
    );
  }
}

/// A tappable date field in the form's input style.
class LpgDateField extends StatelessWidget {
  const LpgDateField({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
    this.errorText,
    this.isRequired = false,
    this.firstDate,
    this.lastDate,
  });

  final String label;
  final DateTime? value;
  final ValueChanged<DateTime> onChanged;
  final String? errorText;
  final bool isRequired;
  final DateTime? firstDate;
  final DateTime? lastDate;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final date = value;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LpgFieldLabel(label, isRequired: isRequired),
        Semantics(
          button: true,
          label: '$label, ${date == null ? 'not set' : LpgFormat.date(date)}',
          excludeSemantics: true,
          child: InkWell(
            borderRadius: BorderRadius.circular(LpgRadius.lg),
            onTap: () async {
              final now = DateTime.now();
              final picked = await showDatePicker(
                context: context,
                initialDate: date ?? now,
                firstDate: firstDate ?? DateTime(2000),
                lastDate: lastDate ?? DateTime(2100),
              );
              if (picked != null) onChanged(picked);
            },
            child: InputDecorator(
              decoration: InputDecoration(
                prefixIcon: const Icon(
                  LpgIcons.calendar,
                  size: LpgSizes.iconMd,
                ),
                errorText: errorText,
              ),
              isEmpty: date == null,
              child: Text(
                date == null ? '' : LpgFormat.date(date),
                style: context.lpgText.bodyLarge?.copyWith(
                  color: colors.textPrimary,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
