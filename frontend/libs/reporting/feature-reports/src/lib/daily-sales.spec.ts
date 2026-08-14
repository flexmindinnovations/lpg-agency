import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DailySales } from './daily-sales';

describe('DailySales', () => {
  let component: DailySales;
  let fixture: ComponentFixture<DailySales>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DailySales],
    }).compileComponents();

    fixture = TestBed.createComponent(DailySales);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
