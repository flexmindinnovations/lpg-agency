import 'dart:async';
import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';

import '../../../providers.dart';
import '../../../widgets/form_field_widgets.dart';
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
    final colors = Theme.of(context).extension<LpgColors>()!;
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => Container(
        decoration: BoxDecoration(
          color: Theme.of(sheetContext).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: colors.borderDefault,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 24),
            LpgListTile(
              leadingIcon: Icons.photo_camera_outlined,
              title: 'Take Photo',
              onTap: () {
                Navigator.of(sheetContext).pop();
                _pickImage(ImageSource.camera);
              },
            ),
            const SizedBox(height: 8),
            LpgListTile(
              leadingIcon: Icons.photo_library_outlined,
              title: 'Choose from Gallery',
              onTap: () {
                Navigator.of(sheetContext).pop();
                _pickImage(ImageSource.gallery);
              },
            ),
          ],
        ),
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
        final messenger = ScaffoldMessenger.of(context);
        Navigator.of(context).pop();
        ref.invalidate(kycDocumentsProvider);
        messenger.showSnackBar(
          const SnackBar(
            content: Text('Document submitted — we\'ll review it shortly.'),
          ),
        );
      },
      onFailure: (failure) => setState(() => _error = failure.message),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Add KYC Document',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_error != null) ...[
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colors.statusDanger.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: colors.statusDanger.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: colors.statusDanger),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _error!,
                          style: TextStyle(
                            color: colors.statusDanger,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
              ],

              const FieldLabel('Document Type'),
              FormDropdownField<String>(
                value: _docType,
                items: _docTypes,
                onChanged: (v) => setState(() {
                  _docType = v!;
                  _ocrHint = null;
                }),
              ),
              const SizedBox(height: 24),

              const FieldLabel('Document Photo'),
              GestureDetector(
                onTap: _uploading ? null : _showImageSourceSheet,
                child: Container(
                  height: 180,
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: colors.surfaceRaised,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: colors.borderDefault),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: _imageBytes == null
                      ? Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.add_a_photo_outlined,
                              size: 32,
                              color: colors.textSecondary,
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Tap to add a photo',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                          ],
                        )
                      : Stack(
                          fit: StackFit.expand,
                          children: [
                            Image.memory(_imageBytes!, fit: BoxFit.cover),
                            if (_uploading)
                              Container(
                                color: Colors.black.withValues(alpha: 0.4),
                                child: const Center(
                                  child: CircularProgressIndicator(
                                    color: Colors.white,
                                  ),
                                ),
                              )
                            else
                              Positioned(
                                right: 8,
                                bottom: 8,
                                child: Material(
                                  color: Colors.black.withValues(alpha: 0.6),
                                  shape: const StadiumBorder(),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 6,
                                    ),
                                    child: Text(
                                      'Change',
                                      style: theme.textTheme.labelSmall
                                          ?.copyWith(color: Colors.white),
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ),
                ),
              ),
              if (_ocrHint != null) ...[
                const SizedBox(height: 8),
                Text(
                  _ocrHint!,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colors.textSecondary,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
              const SizedBox(height: 24),

              LpgTextField(
                label: 'Document Number',
                controller: _numberController,
                validator: (value) =>
                    value == null || value.trim().isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 24),

              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: _DateField(
                      label: 'Issue Date (optional)',
                      value: _issueDate,
                      onTap: () => _pickDate(isExpiry: false),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _DateField(
                      label: 'Expiry Date (optional)',
                      value: _expiryDate,
                      onTap: () => _pickDate(isExpiry: true),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 40),

              LpgButton(
                label: 'Submit Document',
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
    final colors = Theme.of(context).extension<LpgColors>()!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        FieldLabel(label),
        InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: onTap,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: colors.borderDefault),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.calendar_today_outlined,
                  size: 16,
                  color: colors.textSecondary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    value == null
                        ? 'Select'
                        : DateFormat('MMM dd, yyyy').format(value!),
                    style: TextStyle(
                      color: value == null
                          ? colors.textSecondary
                          : colors.textPrimary,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
