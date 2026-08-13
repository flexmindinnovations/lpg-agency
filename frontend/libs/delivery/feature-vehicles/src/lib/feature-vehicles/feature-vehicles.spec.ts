import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { FeatureVehicles } from './feature-vehicles';
import { ApiConfiguration } from '@lpg/shared/data-access';

describe('FeatureVehicles', () => {
  let component: FeatureVehicles;
  let fixture: ComponentFixture<FeatureVehicles>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureVehicles],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureVehicles);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
