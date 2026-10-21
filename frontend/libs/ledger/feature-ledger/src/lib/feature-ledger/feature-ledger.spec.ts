import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { FeatureLedger } from './feature-ledger';

describe('FeatureLedger', () => {
  let component: FeatureLedger;
  let fixture: ComponentFixture<FeatureLedger>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureLedger],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: PERMISSION_CHECKER, useValue: signal(null) },
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureLedger);
    component = fixture.componentInstance;
    // customerId is a required input — supply a placeholder UUID so
    // Angular 22's required-input guard (NG0950) doesn't fire in ngOnInit.
    fixture.componentRef.setInput('customerId', '00000000-0000-0000-0000-000000000000');
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
