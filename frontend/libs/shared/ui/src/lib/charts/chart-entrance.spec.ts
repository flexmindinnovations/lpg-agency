import { TestBed } from '@angular/core/testing';
import { ChartEntranceRegistry } from './chart-entrance.registry';

describe('ChartEntranceRegistry', () => {
  it('lets a chart play its entrance once, and never again', () => {
    const registry = TestBed.inject(ChartEntranceRegistry);
    expect(registry.claim('home.revenue')).toBe(true);
    expect(registry.claim('home.revenue')).toBe(false);
    expect(registry.claim('home.cash')).toBe(true);
  });
});
