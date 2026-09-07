import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ConfirmationService } from 'primeng/api';
import { FeatureEmployees } from './feature-employees';

describe('FeatureEmployees', () => {
  let component: FeatureEmployees;
  let fixture: ComponentFixture<FeatureEmployees>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureEmployees],
      providers: [ConfirmationService],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureEmployees);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
