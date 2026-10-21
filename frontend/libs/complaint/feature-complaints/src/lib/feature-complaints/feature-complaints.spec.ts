import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { FeatureComplaints } from './feature-complaints';

describe('FeatureComplaints', () => {
  let component: FeatureComplaints;
  let fixture: ComponentFixture<FeatureComplaints>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureComplaints],
      providers: [
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
        // NotifyService toasts through the app-wide MessageService.
        MessageService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureComplaints);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
