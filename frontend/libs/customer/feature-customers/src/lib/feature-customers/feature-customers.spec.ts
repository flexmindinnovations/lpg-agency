import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { FeatureCustomers } from './feature-customers';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

describe('FeatureCustomers', () => {
  let component: FeatureCustomers;
  let fixture: ComponentFixture<FeatureCustomers>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureCustomers],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        MessageService,
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap({}) } },
        },
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureCustomers);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
