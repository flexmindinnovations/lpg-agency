import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureDrivers } from './feature-drivers';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

describe('FeatureDrivers', () => {
  let component: FeatureDrivers;
  let fixture: ComponentFixture<FeatureDrivers>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureDrivers],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureDrivers);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
