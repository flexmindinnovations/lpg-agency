# 42 — No delivery before the van is loaded — Plan

## Problem

Reported 2026-10-19: a driver could start a delivery (`ready_for_dispatch ->
out_for_delivery`) while the order's route was still `planned`, because the
office had marked the order ready for dispatch without loading the van
(`POST /routes/{id}/load`, BR-12). The route then never reached
`in_progress`, so every delivery attempt failed with "Cannot record POD:
route is in status 'planned'" and the Driver App put the stop back on Start.

## Changes

- **Application:** new `RouteNotLoadedError` (409 `ROUTE_NOT_LOADED`).
  `DepartOrderUseCase`, `DeliverOrderUseCase` and
  `RecordFailedDeliveryUseCase` refuse an order whose route is `planned`,
  before mutating anything or spending the delivery code. Delivering or
  failing an order whose route is `loaded` (it departed before this gate, and
  the van was loaded afterwards) starts the route, so those stuck orders go
  through once the office loads the van.
- **Driver App:** the stop screen reads the active route's status. While it is
  `planned` it shows "Van not loaded yet" with a "Check again" action instead
  of Start / Record delivery / Delivery failed. An `assigned` stop shows
  "Waiting for dispatch" instead of a Start button the server would reject.
- **Docs:** error catalog row for `ROUTE_NOT_LOADED`.
