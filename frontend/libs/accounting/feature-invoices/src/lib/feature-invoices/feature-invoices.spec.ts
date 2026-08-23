import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { FeatureInvoices } from './feature-invoices';

describe('FeatureInvoices', () => {
  let component: FeatureInvoices;
  let fixture: ComponentFixture<FeatureInvoices>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureInvoices],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureInvoices);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
