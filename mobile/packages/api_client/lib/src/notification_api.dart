import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';
import 'models/models.dart';

/// Hand-written wrapper for the backend's `/notifications/*` routes. Scoped
/// by `principal.user_id` server-side, not a permission code — any
/// authenticated role reads and marks only their own notifications.
final class NotificationApi {
  const NotificationApi(this._dio);

  final Dio _dio;

  /// Fetch a page of the current user's notifications. The response carries
  /// only `items` — no total count — so a "load more" UI should keep paging
  /// while a page comes back with exactly `limit` items.
  Future<Result<PaginatedNotificationResponse>> getMyNotifications({
    int skip = 0,
    int limit = 50,
    bool unreadOnly = false,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/notifications',
        queryParameters: {
          'skip': skip,
          'limit': limit,
          'unread_only': unreadOnly,
        },
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(PaginatedNotificationResponse.fromJson(response.data!));
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<int>> getUnreadCount() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/notifications/unread-count',
      );
      if (response.data == null) {
        return const FailureResult(Failure(message: 'Response data is null'));
      }
      return Success(UnreadCountResponse.fromJson(response.data!).count);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<void>> markRead(String notificationId) async {
    try {
      await _dio.patch<void>('/api/v1/notifications/$notificationId/read');
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }

  Future<Result<void>> markAllRead() async {
    try {
      await _dio.post<void>('/api/v1/notifications/read-all');
      return const Success(null);
    } on DioException catch (e) {
      return FailureResult(mapDioError(e));
    } catch (e) {
      return FailureResult(Failure(message: e.toString()));
    }
  }
}
