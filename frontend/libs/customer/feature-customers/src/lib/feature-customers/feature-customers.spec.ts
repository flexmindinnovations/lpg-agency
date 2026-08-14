import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FeatureCustomers } from './feature-customers';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';

describe('FeatureCustomers', () => {
  let component: FeatureCustomers;
  let fixture: ComponentFixture<FeatureCustomers>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureCustomers],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        MessageService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureCustomers);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
