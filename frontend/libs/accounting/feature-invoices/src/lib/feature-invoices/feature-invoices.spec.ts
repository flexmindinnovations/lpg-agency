import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FeatureInvoices } from './feature-invoices';

describe('FeatureInvoices', () => {
  let component: FeatureInvoices;
  let fixture: ComponentFixture<FeatureInvoices>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureInvoices]
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureInvoices);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
