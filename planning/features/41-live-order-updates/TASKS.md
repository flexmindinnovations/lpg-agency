# 41 — Live order updates and notifications — Tasks

- [x] `OrderStatusChanged` event on every transition
- [x] Realtime handler publishes the real status; `notification.new` carries content
- [x] `ConnectionManager` keeps earlier channels on a second subscribe
- [x] Out-for-delivery, route-started and delivered notifications
- [x] Dashboard: order detail live refresh, bell toast, token-aware reconnect
- [x] Customer app: refresh lists/detail on order notifications
- [x] Driver app: `/ws` + refresh route on notification/push
- [x] Backend unit tests (handlers, connection manager)
- [x] (Fixed 2026-10-21, feature 47) The WebSocket `driver` intent subscribes to `driver:{identity user id}` but
      route events publish `driver:{driver id}`, so that channel never matches.
      Unused by the apps today (the driver app uses `notifications`); fix or
      remove when something needs it.
- [x] (Fixed 2026-10-21, feature 47) The `order:{id}` intent lets any customer in the tenant subscribe to any
      order id (messages carry only id and status). Add an ownership check.
