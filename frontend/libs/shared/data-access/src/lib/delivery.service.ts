import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

import { getDriverApiV1DriversDriverIdGet } from './generated/fn/delivery/get-driver-api-v-1-drivers-driver-id-get';
import { getVehicleApiV1VehiclesVehicleIdGet } from './generated/fn/delivery/get-vehicle-api-v-1-vehicles-vehicle-id-get';
import { listDriversApiV1DriversGet } from './generated/fn/delivery/list-drivers-api-v-1-drivers-get';
import { listVehiclesApiV1VehiclesGet } from './generated/fn/delivery/list-vehicles-api-v-1-vehicles-get';
import { registerDriverApiV1DriversPost } from './generated/fn/delivery/register-driver-api-v-1-drivers-post';
import { registerVehicleApiV1VehiclesPost } from './generated/fn/delivery/register-vehicle-api-v-1-vehicles-post';
import { updateDriverAssignmentApiV1DriversDriverIdAssignmentPatch } from './generated/fn/delivery/update-driver-assignment-api-v-1-drivers-driver-id-assignment-patch';
import { updateDriverLicenseApiV1DriversDriverIdLicensePatch } from './generated/fn/delivery/update-driver-license-api-v-1-drivers-driver-id-license-patch';
import { updateDriverStatusApiV1DriversDriverIdStatusPatch } from './generated/fn/delivery/update-driver-status-api-v-1-drivers-driver-id-status-patch';
import { updateVehicleDetailsApiV1VehiclesVehicleIdDetailsPatch } from './generated/fn/delivery/update-vehicle-details-api-v-1-vehicles-vehicle-id-details-patch';
import { updateVehicleStatusApiV1VehiclesVehicleIdStatusPatch } from './generated/fn/delivery/update-vehicle-status-api-v-1-vehicles-vehicle-id-status-patch';
import { planRouteApiV1RoutesPost } from './generated/fn/routes/plan-route-api-v-1-routes-post';
import { listRoutesApiV1RoutesGet } from './generated/fn/routes/list-routes-api-v-1-routes-get';
import { getRouteApiV1RoutesRouteIdGet } from './generated/fn/routes/get-route-api-v-1-routes-route-id-get';
import { updateRouteStatusApiV1RoutesRouteIdStatusPatch } from './generated/fn/routes/update-route-status-api-v-1-routes-route-id-status-patch';
import { assignOrderApiV1RoutesRouteIdAssignOrderPost } from './generated/fn/routes/assign-order-api-v-1-routes-route-id-assign-order-post';
import { loadVehicleForRouteApiV1RoutesRouteIdLoadPost } from './generated/fn/routes/load-vehicle-for-route-api-v-1-routes-route-id-load-post';
import { completeRouteReconciliationApiV1RoutesRouteIdReconcilePost } from './generated/fn/routes/complete-route-reconciliation-api-v-1-routes-route-id-reconcile-post';
import { declareCashHandoverApiV1CashHandoversPost } from './generated/fn/cash-handovers/declare-cash-handover-api-v-1-cash-handovers-post';

import type { RouteResponse } from './generated/models/route-response';
import type { RoutePageResponse } from './generated/models/route-page-response';
import type { PlanRouteRequest } from './generated/models/plan-route-request';
import type { DriverResponse } from './generated/models/driver-response';
import type { DriverPageResponse } from './generated/models/driver-page-response';
import type { RegisterDriverRequest } from './generated/models/register-driver-request';
import type { UpdateDriverAssignmentRequest } from './generated/models/update-driver-assignment-request';
import type { UpdateDriverLicenseRequest } from './generated/models/update-driver-license-request';
import type { VehicleResponse } from './generated/models/vehicle-response';
import type { VehiclePageResponse } from './generated/models/vehicle-page-response';
import type { RegisterVehicleRequest } from './generated/models/register-vehicle-request';
import type { UpdateVehicleDetailsRequest } from './generated/models/update-vehicle-details-request';
import type { UpdateRouteStatusRequest } from './generated/models/update-route-status-request';
import type { LoadVehicleRequest } from './generated/models/load-vehicle-request';
import type { DeclareCashHandoverRequest } from './generated/models/declare-cash-handover-request';
import type { CashHandoverResponse } from './generated/models/cash-handover-response';

@Injectable({ providedIn: 'root' })
export class DeliveryService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  // ---------------------------------------------------------------------------
  // Driver Operations
  // ---------------------------------------------------------------------------

  registerDriver(request: RegisterDriverRequest): Observable<DriverResponse> {
    return registerDriverApiV1DriversPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body));
  }

  listDrivers(
    skip = 0,
    limit = 50,
    search?: string,
    status?: string,
    branchId?: string,
  ): Observable<DriverPageResponse> {
    return listDriversApiV1DriversGet(this.http, this.config.rootUrl, {
      skip,
      limit,
      search,
      status,
      branch_id: branchId,
    }).pipe(map((res) => res.body));
  }

  getDriver(driverId: string): Observable<DriverResponse> {
    return getDriverApiV1DriversDriverIdGet(this.http, this.config.rootUrl, {
      driver_id: driverId,
    }).pipe(map((res) => res.body));
  }

  updateDriverStatus(driverId: string, status: string): Observable<DriverResponse> {
    return updateDriverStatusApiV1DriversDriverIdStatusPatch(this.http, this.config.rootUrl, {
      driver_id: driverId,
      body: { status },
    }).pipe(map((res) => res.body));
  }

  updateDriverLicense(
    driverId: string,
    request: UpdateDriverLicenseRequest,
  ): Observable<DriverResponse> {
    return updateDriverLicenseApiV1DriversDriverIdLicensePatch(this.http, this.config.rootUrl, {
      driver_id: driverId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  updateDriverAssignment(
    driverId: string,
    request: UpdateDriverAssignmentRequest,
  ): Observable<DriverResponse> {
    return updateDriverAssignmentApiV1DriversDriverIdAssignmentPatch(this.http, this.config.rootUrl, {
      driver_id: driverId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Vehicle Operations
  // ---------------------------------------------------------------------------

  registerVehicle(request: RegisterVehicleRequest): Observable<VehicleResponse> {
    return registerVehicleApiV1VehiclesPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body));
  }

  listVehicles(
    skip = 0,
    limit = 50,
    search?: string,
    status?: string,
    branchId?: string,
  ): Observable<VehiclePageResponse> {
    return listVehiclesApiV1VehiclesGet(this.http, this.config.rootUrl, {
      skip,
      limit,
      search,
      status,
      branch_id: branchId,
    }).pipe(map((res) => res.body));
  }

  getVehicle(vehicleId: string): Observable<VehicleResponse> {
    return getVehicleApiV1VehiclesVehicleIdGet(this.http, this.config.rootUrl, {
      vehicle_id: vehicleId,
    }).pipe(map((res) => res.body));
  }

  updateVehicleStatus(vehicleId: string, status: string): Observable<VehicleResponse> {
    return updateVehicleStatusApiV1VehiclesVehicleIdStatusPatch(this.http, this.config.rootUrl, {
      vehicle_id: vehicleId,
      body: { status },
    }).pipe(map((res) => res.body));
  }

  updateVehicleDetails(
    vehicleId: string,
    request: UpdateVehicleDetailsRequest,
  ): Observable<VehicleResponse> {
    return updateVehicleDetailsApiV1VehiclesVehicleIdDetailsPatch(this.http, this.config.rootUrl, {
      vehicle_id: vehicleId,
      body: request,
    }).pipe(map((res) => res.body));
  }
  // ---------------------------------------------------------------------------
  // Route Operations
  // ---------------------------------------------------------------------------

  planRoute(request: PlanRouteRequest): Observable<RouteResponse> {
    return planRouteApiV1RoutesPost(this.http, this.config.rootUrl, { body: request }).pipe(map((res) => res.body));
  }

  listRoutes(
    page = 1,
    pageSize = 50,
    status?: string,
    branchId?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Observable<RoutePageResponse> {
    return listRoutesApiV1RoutesGet(this.http, this.config.rootUrl, {
      page,
      page_size: pageSize,
      status,
      branch_id: branchId,
      date_from: dateFrom,
      date_to: dateTo,
    }).pipe(map((res) => res.body));
  }

  getRoute(routeId: string): Observable<RouteResponse> {
    return getRouteApiV1RoutesRouteIdGet(this.http, this.config.rootUrl, { route_id: routeId }).pipe(map((res) => res.body));
  }

  updateRouteStatus(
    routeId: string,
    status: UpdateRouteStatusRequest['status'],
  ): Observable<RouteResponse> {
    return updateRouteStatusApiV1RoutesRouteIdStatusPatch(this.http, this.config.rootUrl, {
      route_id: routeId,
      body: { status },
    }).pipe(map((res) => res.body));
  }

  assignOrderToRoute(routeId: string, orderId: string): Observable<RouteResponse> {
    return assignOrderApiV1RoutesRouteIdAssignOrderPost(this.http, this.config.rootUrl, {
      route_id: routeId,
      body: { order_id: orderId },
    }).pipe(map((res) => res.body));
  }

  loadVehicleForRoute(routeId: string, request: LoadVehicleRequest): Observable<RouteResponse> {
    return loadVehicleForRouteApiV1RoutesRouteIdLoadPost(this.http, this.config.rootUrl, {
      route_id: routeId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  completeRouteReconciliation(routeId: string): Observable<RouteResponse> {
    return completeRouteReconciliationApiV1RoutesRouteIdReconcilePost(this.http, this.config.rootUrl, {
      route_id: routeId,
    }).pipe(map((res) => res.body));
  }

  declareCashHandover(request: DeclareCashHandoverRequest): Observable<CashHandoverResponse> {
    return declareCashHandoverApiV1CashHandoversPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body));
  }
}
