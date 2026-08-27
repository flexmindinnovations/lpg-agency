/// Mirrors the backend's `KycDocumentResponse`. `fileUrl` is a short-lived
/// presigned URL resolved by the router at read time (`GET
/// /customers/{id}/kyc`), directly fetchable — not the opaque storage key
/// [KycAttachmentResponse.blobRef] returns from the upload endpoint.
class KycDocumentResponse {
  const KycDocumentResponse({
    required this.id,
    required this.docType,
    required this.documentNumber,
    this.fileUrl,
    this.issueDate,
    this.expiryDate,
    required this.verificationStatus,
    this.rejectionReason,
    this.verifiedAt,
  });

  factory KycDocumentResponse.fromJson(Map<String, dynamic> json) =>
      KycDocumentResponse(
        id: json['id'] as String,
        docType: json['doc_type'] as String,
        documentNumber: json['document_number'] as String,
        fileUrl: json['file_url'] as String?,
        issueDate: json['issue_date'] == null
            ? null
            : DateTime.parse(json['issue_date'] as String),
        expiryDate: json['expiry_date'] == null
            ? null
            : DateTime.parse(json['expiry_date'] as String),
        verificationStatus: json['verification_status'] as String,
        rejectionReason: json['rejection_reason'] as String?,
        verifiedAt: json['verified_at'] == null
            ? null
            : DateTime.parse(json['verified_at'] as String),
      );

  final String id;
  final String docType;
  final String documentNumber;
  final String? fileUrl;
  final DateTime? issueDate;
  final DateTime? expiryDate;
  final String verificationStatus;
  final String? rejectionReason;
  final DateTime? verifiedAt;
}

/// `GET /customers/{id}/kyc` response wrapper — mirrors the backend's
/// `KycDocumentListResponse`. Full list only, not paginated.
class KycDocumentListResponse {
  const KycDocumentListResponse({required this.items});

  factory KycDocumentListResponse.fromJson(Map<String, dynamic> json) =>
      KycDocumentListResponse(
        items: (json['items'] as List<dynamic>)
            .map((e) => KycDocumentResponse.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  final List<KycDocumentResponse> items;
}

/// `POST /customers/kyc-attachments` response — the opaque storage key for a
/// just-uploaded image, to be passed as [SubmitKycDocumentRequest.fileUrl]
/// or [RecognizeKycDocumentRequest.blobRef]. Not a fetchable URL despite the
/// backend field name `blob_ref` (compare [KycDocumentResponse.fileUrl],
/// which is).
class KycAttachmentResponse {
  const KycAttachmentResponse({required this.blobRef});

  factory KycAttachmentResponse.fromJson(Map<String, dynamic> json) =>
      KycAttachmentResponse(blobRef: json['blob_ref'] as String);

  final String blobRef;
}

/// `POST /customers/{id}/kyc` body — mirrors the backend's
/// `SubmitKycDocumentRequest`. `fileUrl` should be the `blobRef` returned by
/// the upload endpoint.
class SubmitKycDocumentRequest {
  const SubmitKycDocumentRequest({
    required this.docType,
    required this.documentNumber,
    this.fileUrl,
    this.issueDate,
    this.expiryDate,
  });

  final String docType;
  final String documentNumber;
  final String? fileUrl;
  final DateTime? issueDate;
  final DateTime? expiryDate;

  Map<String, dynamic> toJson() => {
    'doc_type': docType,
    'document_number': documentNumber,
    if (fileUrl != null) 'file_url': fileUrl,
    if (issueDate != null)
      'issue_date': issueDate!.toIso8601String().split('T').first,
    if (expiryDate != null)
      'expiry_date': expiryDate!.toIso8601String().split('T').first,
  };
}

/// `POST /customers/kyc-attachments/recognize` body — mirrors the backend's
/// `RecognizeKycDocumentRequest`.
class RecognizeKycDocumentRequest {
  const RecognizeKycDocumentRequest({required this.blobRef});

  final String blobRef;

  Map<String, dynamic> toJson() => {'blob_ref': blobRef};
}

/// `POST /customers/kyc-attachments/recognize` response — mirrors the
/// backend's `RecognizeKycDocumentResponse`. `confidence` scores the OCR
/// pass as a whole; the docstring on the backend schema notes the
/// `address*` fields are a best-effort split of freeform OCR text and are
/// less reliable than the other fields — keep them editable in the UI
/// regardless of what auto-fills.
class RecognizeKycDocumentResponse {
  const RecognizeKycDocumentResponse({
    this.docType,
    this.documentNumber,
    this.fullName,
    this.dateOfBirth,
    required this.confidence,
    this.addressLine1,
    this.addressLine2,
    this.addressLandmark,
    this.addressArea,
    this.addressCity,
    this.addressDistrict,
    this.addressState,
    this.addressPincode,
  });

  factory RecognizeKycDocumentResponse.fromJson(Map<String, dynamic> json) =>
      RecognizeKycDocumentResponse(
        docType: json['doc_type'] as String?,
        documentNumber: json['document_number'] as String?,
        fullName: json['full_name'] as String?,
        dateOfBirth: json['date_of_birth'] == null
            ? null
            : DateTime.parse(json['date_of_birth'] as String),
        confidence: (json['confidence'] as num).toDouble(),
        addressLine1: json['address_line_1'] as String?,
        addressLine2: json['address_line_2'] as String?,
        addressLandmark: json['address_landmark'] as String?,
        addressArea: json['address_area'] as String?,
        addressCity: json['address_city'] as String?,
        addressDistrict: json['address_district'] as String?,
        addressState: json['address_state'] as String?,
        addressPincode: json['address_pincode'] as String?,
      );

  final String? docType;
  final String? documentNumber;
  final String? fullName;
  final DateTime? dateOfBirth;
  final double confidence;
  final String? addressLine1;
  final String? addressLine2;
  final String? addressLandmark;
  final String? addressArea;
  final String? addressCity;
  final String? addressDistrict;
  final String? addressState;
  final String? addressPincode;
}
