import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { FeatureInventory } from './feature-inventory';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

describe('FeatureInventory', () => {
  let component: FeatureInventory;
  let fixture: ComponentFixture<FeatureInventory>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureInventory],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureInventory);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
