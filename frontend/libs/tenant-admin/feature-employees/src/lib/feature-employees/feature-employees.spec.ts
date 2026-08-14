import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FeatureEmployees } from './feature-employees';

describe('FeatureEmployees', () => {
  let component: FeatureEmployees;
  let fixture: ComponentFixture<FeatureEmployees>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureEmployees],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureEmployees);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
