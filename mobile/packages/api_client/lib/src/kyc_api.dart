import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the KYC routes on the backend's `/customers/*`
/// router (there is no separate `kyc.py` router). `verify` is deliberately
/// not wrapped here: the backend hard-blocks it for `customer`-role
/// principals regardless of permission grants (`customer.py`'s
/// `verify_kyc` — "Customers cannot verify KYC documents.").
final class KycApi {
  const KycApi(this._dio);

  final Dio _dio;

  Future<Result<KycDocumentListResponse>> getMyDocuments(
    String customerId,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/customers/$customerId/kyc',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(KycDocumentListResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Pre-upload a document image, returning an opaque `blobRef` to pass to
  /// [recognizeDocument] and/or [submitDocument]. Deliberately
  /// customer-agnostic server-side (staged under a tenant key, not a
  /// customer one) — usable during onboarding before a `Customer` record
  /// exists.
  Future<Result<KycAttachmentResponse>> uploadAttachment({
    required List<int> bytes,
    required String filename,
    String contentType = 'image/jpeg',
  }) async {
    try {
      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          bytes,
          filename: filename,
          contentType: MediaType.parse(contentType),
        ),
      });
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/customers/kyc-attachments',
        data: formData,
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(KycAttachmentResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Best-effort OCR pre-fill from an uploaded image. `confidence` and the
  /// individual field values should drive which fields the UI leaves
  /// editable, per [RecognizeKycDocumentResponse]'s own docs — never
  /// auto-submit without the customer reviewing this.
  Future<Result<RecognizeKycDocumentResponse>> recognizeDocument(
    String blobRef,
  ) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/customers/kyc-attachments/recognize',
        data: RecognizeKycDocumentRequest(blobRef: blobRef).toJson(),
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(RecognizeKycDocumentResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  /// Submit a KYC document record. Returns the new document's id — the
  /// backend responds with a bare UUID, not a wrapped object.
  Future<Result<String>> submitDocument(
    String customerId,
    SubmitKycDocumentRequest request,
  ) async {
    try {
      // Not `_dio.post<String>` — see the comment on
      // `CustomerApi.addCustomerAddress` for why that would leave the
      // response's surrounding JSON quote characters attached.
      final response = await _dio.post<dynamic>(
        '/api/v1/customers/$customerId/kyc',
        data: request.toJson(),
      );
      final id = response.data;
      if (id is! String) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(id);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
