import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('KycApi', () {
    test('getMyDocuments parses the items-only list response', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'items': [
            {
              'id': 'doc-1',
              'doc_type': 'aadhaar',
              'document_number': '1234-5678-9012',
              'file_url': 'https://storage.test/signed-url',
              'verification_status': 'pending',
            },
          ],
        }, 200),
      );
      final kycApi = KycApi(client.dio);

      final result = await kycApi.getMyDocuments('customer-1');

      final list = result.when(onSuccess: (l) => l, onFailure: (_) => null);
      expect(list, isNotNull);
      expect(list!.items.single.verificationStatus, 'pending');
    });

    test(
      'uploadAttachment posts multipart form data and returns the blobRef',
      () async {
        RequestOptions? capturedOptions;
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          capturedOptions = options;
          return jsonResponse({
            'blob_ref': 'tenant/t1/kyc-staging/abc_id.jpg',
          }, 201);
        });
        final kycApi = KycApi(client.dio);

        final result = await kycApi.uploadAttachment(
          bytes: utf8.encode('fake-image-bytes'),
          filename: 'id.jpg',
        );

        expect(capturedOptions!.path, '/api/v1/customers/kyc-attachments');
        expect(capturedOptions!.data, isA<FormData>());
        expect(
          result.when(onSuccess: (r) => r.blobRef, onFailure: (_) => null),
          'tenant/t1/kyc-staging/abc_id.jpg',
        );
      },
    );

    test('recognizeDocument parses OCR fields and confidence', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'full_name': 'Jane Doe',
          'confidence': 0.87,
          'address_city': 'Pune',
        }, 200),
      );
      final kycApi = KycApi(client.dio);

      final result = await kycApi.recognizeDocument(
        'tenant/t1/kyc-staging/abc.jpg',
      );

      final response = result.when(onSuccess: (r) => r, onFailure: (_) => null);
      expect(response, isNotNull);
      expect(response!.fullName, 'Jane Doe');
      expect(response.confidence, 0.87);
      expect(response.documentNumber, isNull);
    });

    test('submitDocument returns the bare document id', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        // FastAPI's `response_model=uuid.UUID` serializes as a JSON string
        // with a `Content-Type: application/json` header — `jsonResponse`
        // matches that, unlike a raw quoted `ResponseBody.fromString`.
        (options) => jsonResponse('doc-new', 201),
      );
      final kycApi = KycApi(client.dio);

      final result = await kycApi.submitDocument(
        'customer-1',
        const SubmitKycDocumentRequest(
          docType: 'aadhaar',
          documentNumber: '1234-5678-9012',
        ),
      );

      expect(
        result.when(onSuccess: (id) => id, onFailure: (_) => null),
        'doc-new',
      );
    });
  });
}
