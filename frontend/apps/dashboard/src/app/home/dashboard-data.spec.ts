import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { NEVER, Subject, of } from 'rxjs';
import {
  AuthService,
  CashHandoverService,
  CustomerService,
  DashboardService,
  InventoryService,
  ReportingService,
  TdtRatingService,
  WebSocketService,
} from '@lpg/shared/data-access';
import { DashboardData } from './dashboard-data';

describe('DashboardData', () => {
  const principal = signal<unknown>({ userId: 'u1', tenantId: 't1', branchId: null });
  let calls: Record<string, jest.Mock>;
  let changes: Subject<unknown>;

  function setup() {
    calls = {
      operations: jest.fn(() => of({ orders: { delivered_today: 1 } })),
      summary: jest.fn(() => of({ inventory_by_status: {} })),
      sales: jest.fn(() => of([])),
      drivers: jest.fn(() => of([])),
      cash: jest.fn(() => of({ total_cash: '0', drivers: [] })),
      reorder: jest.fn(() => of([])),
      rating: jest.fn(() => of({ overall_stars: null })),
      refills: jest.fn(() => of({ items: [] })),
    };
    changes = new Subject();
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: { principal } },
        {
          provide: DashboardService,
          useValue: { getOperations: calls['operations'], getSummary: calls['summary'] },
        },
        {
          provide: ReportingService,
          useValue: { dailySales: calls['sales'], driverPerformance: calls['drivers'] },
        },
        { provide: CashHandoverService, useValue: { cashInHand: calls['cash'] } },
        { provide: InventoryService, useValue: { listReorderSignals: calls['reorder'] } },
        { provide: TdtRatingService, useValue: { getLiveProjection: calls['rating'] } },
        { provide: CustomerService, useValue: { listRefillDue: calls['refills'] } },
        {
          provide: WebSocketService,
          useValue: { subscribeTo: jest.fn(), changes$: () => changes.asObservable() },
        },
      ],
    });
    return TestBed.inject(DashboardData);
  }

  const total = () => Object.values(calls).reduce((sum, fn) => sum + fn.mock.calls.length, 0);

  afterEach(() => {
    jest.restoreAllMocks();
    principal.set({ userId: 'u1', tenantId: 't1', branchId: null });
  });

  it('fetches everything the first time Home opens', () => {
    const data = setup();
    data.connect();
    expect(total()).toBe(8);
    expect(data.operations.data()).not.toBeNull();
    expect(data.isRevisit).toBe(false);
  });

  it('shows the cache and calls the API again for nothing when you come straight back', () => {
    const data = setup();
    data.connect()();
    data.connect();
    expect(total()).toBe(8);
    expect(data.operations.data()).not.toBeNull();
    expect(data.isRevisit).toBe(true);
  });

  it("refreshes today's figures once they are stale, and keeps the slower ones longer", () => {
    const data = setup();
    const now = Date.now();
    const clock = jest.spyOn(Date, 'now').mockReturnValue(now);
    data.connect()();

    clock.mockReturnValue(now + 40_000);
    data.connect()();
    expect(calls['operations']).toHaveBeenCalledTimes(2);
    expect(calls['sales']).toHaveBeenCalledTimes(1);

    clock.mockReturnValue(now + 200_000);
    data.connect();
    expect(calls['sales']).toHaveBeenCalledTimes(2);
  });

  it('keeps showing the old numbers while a refresh is on its way', () => {
    const data = setup();
    const now = Date.now();
    const clock = jest.spyOn(Date, 'now').mockReturnValue(now);
    data.connect()();
    calls['operations'].mockReturnValue(NEVER);

    clock.mockReturnValue(now + 40_000);
    data.connect();
    expect(data.operations.data()).not.toBeNull();
    expect(data.operations.status()).toBe('ready');
  });

  it('asks again for a widget that has nothing yet instead of trusting the clock', () => {
    const data = setup();
    calls['rating'].mockReturnValueOnce(NEVER);
    data.connect()();
    expect(data.rating.data()).toBeNull();
    data.connect();
    expect(calls['rating']).toHaveBeenCalledTimes(1);
  });

  it("never shows one user's figures to another", () => {
    const data = setup();
    data.connect()();
    principal.set({ userId: 'u2', tenantId: 't1', branchId: null });
    data.connect();
    expect(total()).toBe(16);
    expect(data.isRevisit).toBe(false);
  });

  it('refreshes after a live change, only while Home is open', () => {
    jest.useFakeTimers();
    const data = setup();
    const disconnect = data.connect();
    calls['operations'].mockClear();

    changes.next(1);
    jest.advanceTimersByTime(1000);
    expect(calls['operations']).toHaveBeenCalledTimes(1);

    disconnect();
    changes.next(1);
    jest.advanceTimersByTime(1000);
    expect(calls['operations']).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });
});
