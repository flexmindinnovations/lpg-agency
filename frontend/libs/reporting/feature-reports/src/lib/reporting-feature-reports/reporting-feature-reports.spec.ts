import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ReportingFeatureReports } from './reporting-feature-reports';

describe('ReportingFeatureReports', () => {
  let component: ReportingFeatureReports;
  let fixture: ComponentFixture<ReportingFeatureReports>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ReportingFeatureReports],
    }).compileComponents();

    fixture = TestBed.createComponent(ReportingFeatureReports);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
