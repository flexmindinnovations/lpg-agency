/// Mirrors the backend's `NotificationResponse`.
class NotificationResponse {
  const NotificationResponse({
    required this.id,
    required this.tenantId,
    required this.notificationType,
    required this.title,
    required this.body,
    this.referenceType,
    this.referenceId,
    required this.isRead,
    required this.createdAt,
  });

  factory NotificationResponse.fromJson(Map<String, dynamic> json) =>
      NotificationResponse(
        id: json['id'] as String,
        tenantId: json['tenant_id'] as String,
        notificationType: json['notification_type'] as String,
        title: json['title'] as String,
        body: json['body'] as String,
        referenceType: json['reference_type'] as String?,
        referenceId: json['reference_id'] as String?,
        isRead: json['is_read'] as bool,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  final String id;
  final String tenantId;
  final String notificationType;
  final String title;
  final String body;
  final String? referenceType;
  final String? referenceId;
  final bool isRead;
  final DateTime createdAt;
}

/// `GET /notifications` response wrapper — mirrors the backend's
/// `PaginatedNotificationResponse`. Unlike [ComplaintListResponse]/
/// `InvoicePageResponse`, this carries only `items` — no `total`, and no
/// `skip`/`limit` echoed back. A "load more" UI must page until a response
/// comes back shorter than the requested `limit`; there is no total count
/// to show. Use [UnreadCountResponse] for the unread badge instead.
class PaginatedNotificationResponse {
  const PaginatedNotificationResponse({required this.items});

  factory PaginatedNotificationResponse.fromJson(Map<String, dynamic> json) =>
      PaginatedNotificationResponse(
        items: (json['items'] as List<dynamic>)
            .map(
              (e) => NotificationResponse.fromJson(e as Map<String, dynamic>),
            )
            .toList(),
      );

  final List<NotificationResponse> items;
}

/// `GET /notifications/unread-count` response.
class UnreadCountResponse {
  const UnreadCountResponse({required this.count});

  factory UnreadCountResponse.fromJson(Map<String, dynamic> json) =>
      UnreadCountResponse(count: json['count'] as int);

  final int count;
}
