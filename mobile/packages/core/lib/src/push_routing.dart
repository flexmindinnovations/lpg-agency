/// The push-notification deep-link contract, shared by the three apps.
///
/// The backend sends every push (and every `notification.new` realtime
/// message) with the same data block: `type` (the catalog key, e.g.
/// `delivery_confirmed`), plus `reference_type` / `reference_id` naming the
/// thing it is about (`order`, `invoice`, `route`, `complaint`,
/// `cash_handover`, ...). See ADR-069. Each app turns that pair into one of
/// its own routes with [notificationRoute]; the same function serves a tap
/// on a push, a tap on a tray notification and a tap on an inbox row, so all
/// three always land on the same screen.
library;

/// Which app is resolving the link.
enum PushApp { customer, driver, admin }

/// The route a notification opens in [app], or `null` when [referenceType]
/// and [referenceId] are both missing (nothing to open). A notification that
/// has data but no screen of its own opens the app's inbox.
String? notificationRoute(
  PushApp app, {
  String? referenceType,
  String? referenceId,
}) {
  final type = (referenceType == null || referenceType.isEmpty)
      ? null
      : referenceType;
  final id = (referenceId == null || referenceId.isEmpty) ? null : referenceId;
  if (type == null && id == null) return null;

  switch (app) {
    case PushApp.customer:
      return switch ((type, id)) {
        ('order', final String id) => '/orders/$id',
        ('invoice', final String id) => '/orders/invoices/$id',
        ('complaint', final String id) => '/support/$id',
        _ => '/notifications',
      };
    case PushApp.driver:
      return switch ((type, id)) {
        ('order', final String id) => '/deliveries/stops/$id',
        _ => '/',
      };
    case PushApp.admin:
      return switch ((type, id)) {
        ('order', final String id) => '/orders/$id',
        ('route', final String id) => '/dispatch/trip/$id',
        ('complaint', final String id) => '/complaints/$id',
        ('invoice', final String id) => '/invoices/$id',
        ('customer', final String id) => '/customers/$id',
        ('cash_handover', _) => '/approvals',
        ('price_list_proposal', _) => '/pricing',
        ('compliance_document', _) => '/compliance',
        ('inventory_location', _) => '/stock',
        _ => '/alerts',
      };
  }
}

/// Holds a deep link until the app can act on it.
///
/// A notification can be tapped while the app is still restoring its session
/// (cold start), while the user is signed out, or while it is running. Going
/// to the route straight away in the first two cases is wrong: the router's
/// auth guard sends the user to the splash/login screen and the target is
/// lost. [open] navigates immediately when signed in and otherwise remembers
/// the route; [flush] (call it whenever the auth state changes) performs the
/// pending navigation once the user is signed in.
class DeepLinkGate {
  DeepLinkGate({required this.isAuthenticated, required this.go});

  final bool Function() isAuthenticated;
  final void Function(String route) go;

  String? _pending;

  /// The route waiting for sign-in, if any.
  String? get pending => _pending;

  void open(String route) {
    if (isAuthenticated()) {
      _pending = null;
      go(route);
    } else {
      _pending = route;
    }
  }

  void flush() {
    final route = _pending;
    if (route == null || !isAuthenticated()) return;
    _pending = null;
    go(route);
  }
}
