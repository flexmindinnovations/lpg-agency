import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { FeatureDrivers } from './feature-drivers';
import { ApiConfiguration } from '@lpg/shared/data-access';

describe('FeatureDrivers', () => {
  let component: FeatureDrivers;
  let fixture: ComponentFixture<FeatureDrivers>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureDrivers],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureDrivers);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
