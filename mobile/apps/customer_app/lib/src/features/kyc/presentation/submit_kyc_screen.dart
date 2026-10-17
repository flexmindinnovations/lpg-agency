import 'dart:async';
import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../providers.dart';
import '../../profile/data/profile_provider.dart';
import '../data/kyc_provider.dart';

const _docTypes = <String, String>{
  'aadhaar': 'Aadhaar Card',
  'pan': 'PAN Card',
  'voter_id': 'Voter ID',
  'driving_license': 'Driving License',
  'passport': 'Passport',
};

/// Only these two are recognized by the backend's OCR pass
/// (`kyc_document_parser.py`'s `parse_kyc_document` checks for an Aadhaar
/// or PAN pattern and returns `doc_type: None` for anything else) -- other
/// doc types still upload and submit fine, they just don't get the
/// auto-fill assist.
const _ocrSupportedDocTypes = {'aadhaar', 'pan'};

class SubmitKycScreen extends ConsumerStatefulWidget {
  const SubmitKycScreen({super.key});

  @override
  ConsumerState<SubmitKycScreen> createState() => _SubmitKycScreenState();
}

class _SubmitKycScreenState extends ConsumerState<SubmitKycScreen> {
  final _formKey = GlobalKey<FormState>();
  final _numberController = TextEditingController();
  final _picker = ImagePicker();

  String _docType = 'aadhaar';
  DateTime? _issueDate;
  DateTime? _expiryDate;

  Uint8List? _imageBytes;
  String? _blobRef;
  bool _uploading = false;
  bool _submitting = false;
  String? _error;
  String? _ocrHint;

  @override
  void dispose() {
    _numberController.dispose();
    super.dispose();
  }

  Future<void> _pickImage(ImageSource source) async {
    final file = await _picker.pickImage(source: source, imageQuality: 85);
    if (file == null) return;

    final bytes = await file.readAsBytes();
    setState(() {
      _imageBytes = bytes;
      _blobRef = null;
      _ocrHint = null;
      _uploading = true;
      _error = null;
    });

    final result = await ref
        .read(kycApiProvider)
        .uploadAttachment(
          bytes: bytes,
          filename: file.name,
          contentType: 'image/jpeg',
        );

    if (!mounted) return;
    result.when(
      onSuccess: (attachment) {
        setState(() {
          _blobRef = attachment.blobRef;
          _uploading = false;
        });
        // Best-effort auto-fill -- fire and forget from the form's
        // perspective, never blocks the customer from typing the fields in
        // manually while this is still running.
        if (_ocrSupportedDocTypes.contains(_docType)) {
          unawaited(_tryRecognize(attachment.blobRef));
        }
      },
      onFailure: (failure) {
        setState(() {
          _uploading = false;
          _error = 'Could not upload the photo: ${failure.message}';
        });
      },
    );
  }

  Future<void> _tryRecognize(String blobRef) async {
    final result = await ref.read(kycApiProvider).recognizeDocument(blobRef);
    if (!mounted) return;
    result.when(
      onSuccess: (recognized) {
        // The address_* fields are explicitly the least reliable part of
        // this response (per RecognizeKycDocumentResponse's own docs) and
        // this form has nowhere to put them anyway -- only doc_type/
        // document_number get auto-filled, and only into fields the
        // customer hasn't already typed something into.
        setState(() {
          if (recognized.docType != null &&
              _docTypes.containsKey(recognized.docType)) {
            _docType = recognized.docType!;
          }
          if (recognized.documentNumber != null &&
              _numberController.text.trim().isEmpty) {
            _numberController.text = recognized.documentNumber!;
          }
          _ocrHint = recognized.confidence >= 0.5
              ? 'Auto-filled from your photo — please double-check before submitting.'
              : "Couldn't read the document clearly — please fill this in manually.";
        });
      },
      // Recognition is a nice-to-have; a failure here just means the
      // customer fills the form in by hand, same as any doc type OCR
      // doesn't support.
      onFailure: (_) {},
    );
  }

  Future<void> _showImageSourceSheet() async {
    await LpgFeedback.showSheet<void>(
      context,
      title: 'Add a photo',
      builder: (sheetContext) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgListTile(
            leadingIcon: LpgIcons.camera,
            title: 'Take Photo',
            onTap: () {
              Navigator.of(sheetContext).pop();
              _pickImage(ImageSource.camera);
            },
          ),
          LpgListTile(
            leadingIcon: LpgIcons.gallery,
            title: 'Choose from Gallery',
            onTap: () {
              Navigator.of(sheetContext).pop();
              _pickImage(ImageSource.gallery);
            },
          ),
        ],
      ),
    );
  }

  Future<void> _pickDate({required bool isExpiry}) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: isExpiry ? now.add(const Duration(days: 365)) : now,
      firstDate: isExpiry ? now : DateTime(1900),
      lastDate: isExpiry ? DateTime(2100) : now,
    );
    if (picked == null) return;
    setState(() {
      if (isExpiry) {
        _expiryDate = picked;
      } else {
        _issueDate = picked;
      }
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_blobRef == null) {
      setState(
        () => _error = 'Please add a photo of your document before submitting.',
      );
      return;
    }

    final profile = ref.read(profileProvider).value;
    if (profile == null) {
      setState(() => _error = 'Your profile has not loaded yet.');
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    final result = await ref
        .read(kycApiProvider)
        .submitDocument(
          profile.id,
          SubmitKycDocumentRequest(
            docType: _docType,
            documentNumber: _numberController.text.trim(),
            fileUrl: _blobRef,
            issueDate: _issueDate,
            expiryDate: _expiryDate,
          ),
        );

    if (!mounted) return;
    setState(() => _submitting = false);
    result.when(
      onSuccess: (_) {
        // Toast against the screen underneath, which outlives this one.
        final navigator = Navigator.of(context);
        final below = navigator.context;
        navigator.pop();
        ref.invalidate(kycDocumentsProvider);
        LpgFeedback.showToast(
          below,
          'Document submitted — we\'ll review it shortly.',
          tone: LpgTone.success,
        );
      },
      onFailure: (failure) => setState(() => _error = failure.message),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add KYC Document')),
      body: SingleChildScrollView(
        padding: LpgSpacing.page,
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_error != null) ...[
                LpgBanner(tone: LpgTone.danger, message: _error!),
                const SizedBox(height: LpgSpacing.lg),
              ],
              LpgDropdownField<String>(
                label: 'Document type',
                prefixIcon: LpgIcons.kyc,
                value: _docType,
                items: _docTypes,
                onChanged: (v) => setState(() {
                  _docType = v!;
                  _ocrHint = null;
                }),
              ),
              const SizedBox(height: LpgSpacing.lg),
              const LpgFieldLabel('Document photo', isRequired: true),
              _PhotoPicker(
                imageBytes: _imageBytes,
                uploading: _uploading,
                onTap: _uploading ? null : _showImageSourceSheet,
              ),
              if (_ocrHint != null) ...[
                const SizedBox(height: LpgSpacing.sm),
                LpgBanner(
                  tone: LpgTone.info,
                  icon: LpgIcons.sparkle,
                  message: _ocrHint!,
                ),
              ],
              const SizedBox(height: LpgSpacing.lg),
              LpgTextField(
                label: 'Document number',
                isRequired: true,
                prefixIcon: LpgIcons.number,
                textCapitalization: TextCapitalization.characters,
                controller: _numberController,
                validator: (value) =>
                    value == null || value.trim().isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: LpgSpacing.lg),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: _DateField(
                      label: 'Issue date',
                      value: _issueDate,
                      onTap: () => _pickDate(isExpiry: false),
                    ),
                  ),
                  const SizedBox(width: LpgSpacing.md),
                  Expanded(
                    child: _DateField(
                      label: 'Expiry date',
                      value: _expiryDate,
                      onTap: () => _pickDate(isExpiry: true),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: LpgSpacing.xl),
              LpgButton(
                label: 'Submit Document',
                icon: LpgIcons.upload,
                onPressed: _submit,
                isLoading: _submitting,
                expand: true,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The document photo slot: an empty dashed-feel prompt, then the picked
/// image with an upload overlay or a "Change" chip.
class _PhotoPicker extends StatelessWidget {
  const _PhotoPicker({
    required this.imageBytes,
    required this.uploading,
    required this.onTap,
  });

  final Uint8List? imageBytes;
  final bool uploading;
  final VoidCallback? onTap;

  static const _height = 180.0;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final bytes = imageBytes;
    return Semantics(
      button: true,
      label: bytes == null ? 'Add a document photo' : 'Change document photo',
      child: LpgCard(
        variant: bytes == null ? LpgCardVariant.tonal : LpgCardVariant.outlined,
        padding: EdgeInsets.zero,
        onTap: onTap,
        child: SizedBox(
          height: _height,
          width: double.infinity,
          child: bytes == null
              ? Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const LpgIconBox(icon: LpgIcons.addPhoto),
                    const SizedBox(height: LpgSpacing.sm),
                    Text('Tap to add a photo', style: text.titleSmall),
                    const SizedBox(height: LpgSpacing.xs),
                    Text(
                      'Aadhaar and PAN details fill in automatically',
                      style: text.bodySmall?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                  ],
                )
              : ClipRRect(
                  borderRadius: BorderRadius.circular(LpgRadius.xl),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.memory(bytes, fit: BoxFit.cover),
                      if (uploading)
                        ColoredBox(
                          color: colors.surfaceOverlay.withValues(alpha: 0.7),
                          child: const Center(child: LpgLoadingIndicator()),
                        )
                      else
                        Positioned(
                          right: LpgSpacing.sm,
                          bottom: LpgSpacing.sm,
                          child: Chip(
                            avatar: const Icon(
                              LpgIcons.camera,
                              size: LpgSizes.iconSm,
                            ),
                            label: const Text('Change'),
                            backgroundColor: colors.card,
                          ),
                        ),
                    ],
                  ),
                ),
        ),
      ),
    );
  }
}

class _DateField extends StatelessWidget {
  const _DateField({
    required this.label,
    required this.value,
    required this.onTap,
  });

  final String label;
  final DateTime? value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final date = value;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LpgFieldLabel(label),
        Semantics(
          button: true,
          label: '$label, ${date == null ? 'not set' : LpgFormat.date(date)}',
          excludeSemantics: true,
          child: InkWell(
            borderRadius: BorderRadius.circular(LpgRadius.lg),
            onTap: onTap,
            child: InputDecorator(
              decoration: const InputDecoration(
                prefixIcon: Icon(LpgIcons.calendar, size: LpgSizes.iconMd),
                hintText: 'Optional',
              ),
              isEmpty: date == null,
              child: Text(
                date == null ? '' : LpgFormat.date(date),
                style: context.lpgText.bodyLarge?.copyWith(
                  color: colors.textPrimary,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
