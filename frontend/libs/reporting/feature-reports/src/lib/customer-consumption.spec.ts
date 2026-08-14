import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CustomerConsumption } from './customer-consumption';

describe('CustomerConsumption', () => {
  let component: CustomerConsumption;
  let fixture: ComponentFixture<CustomerConsumption>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CustomerConsumption],
    }).compileComponents();

    fixture = TestBed.createComponent(CustomerConsumption);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
