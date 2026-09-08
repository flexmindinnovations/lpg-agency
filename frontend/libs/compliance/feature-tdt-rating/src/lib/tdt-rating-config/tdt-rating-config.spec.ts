import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { MessageService } from 'primeng/api';
import { TdtRatingConfig } from './tdt-rating-config';
import { ApiConfiguration } from '@lpg/shared/data-access';

describe('TdtRatingConfig', () => {
  let component: TdtRatingConfig;
  let fixture: ComponentFixture<TdtRatingConfig>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TdtRatingConfig],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TdtRatingConfig);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('seeds a 5-row band template ending in an unbounded catch-all', () => {
    const rows = component['bands'].controls;
    expect(rows).toHaveLength(5);
    expect(rows[rows.length - 1].controls.maxDays.value).toBeNull();
    expect(rows[rows.length - 1].controls.stars.value).toBe(1);
  });

  it('flags a non-ascending max_days ordering before submit', () => {
    const rows = component['bands'].controls;
    rows[0].controls.maxDays.setValue(10);
    rows[1].controls.maxDays.setValue(2); // now out of order vs. row 0
    expect(component['bandOrderError']()).not.toBeNull();
  });

  it('accepts the seeded default ordering as valid', () => {
    expect(component['bandOrderError']()).toBeNull();
  });

  it('adds a new band just before the catch-all row, and blocks removing the catch-all', () => {
    component['addBand']();
    const rows = component['bands'].controls;
    expect(rows).toHaveLength(6);
    expect(rows[rows.length - 1].controls.maxDays.value).toBeNull(); // catch-all still last

    component['removeBand'](rows.length - 1); // attempting to remove the catch-all row
    expect(component['bands'].controls).toHaveLength(6); // refused — still 6, catch-all untouched
  });

  it('adds and removes fine schedule rows', () => {
    expect(component['fineRules'].length).toBe(0);
    component['addFineRule']();
    expect(component['fineRules'].length).toBe(1);
    component['removeFineRule'](0);
    expect(component['fineRules'].length).toBe(0);
  });
});
