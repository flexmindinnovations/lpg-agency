import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FeatureComplaints } from './feature-complaints';

describe('FeatureComplaints', () => {
  let component: FeatureComplaints;
  let fixture: ComponentFixture<FeatureComplaints>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureComplaints],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureComplaints);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
