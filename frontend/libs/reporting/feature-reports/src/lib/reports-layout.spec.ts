import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ReportsLayout } from './reports-layout';

describe('ReportsLayout', () => {
  let component: ReportsLayout;
  let fixture: ComponentFixture<ReportsLayout>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ReportsLayout],
    }).compileComponents();

    fixture = TestBed.createComponent(ReportsLayout);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
