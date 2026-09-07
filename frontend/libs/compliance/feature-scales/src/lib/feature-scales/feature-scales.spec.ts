import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { FeatureScales } from './feature-scales';
import { ApiConfiguration } from '@lpg/shared/data-access';

describe('FeatureScales', () => {
  let component: FeatureScales;
  let fixture: ComponentFixture<FeatureScales>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureScales],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureScales);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
