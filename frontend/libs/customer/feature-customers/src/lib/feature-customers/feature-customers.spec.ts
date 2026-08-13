import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FeatureCustomers } from './feature-customers';

describe('FeatureCustomers', () => {
  let component: FeatureCustomers;
  let fixture: ComponentFixture<FeatureCustomers>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureCustomers],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureCustomers);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
