import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DriverPerformance } from './driver-performance';

describe('DriverPerformance', () => {
  let component: DriverPerformance;
  let fixture: ComponentFixture<DriverPerformance>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DriverPerformance],
    }).compileComponents();

    fixture = TestBed.createComponent(DriverPerformance);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
