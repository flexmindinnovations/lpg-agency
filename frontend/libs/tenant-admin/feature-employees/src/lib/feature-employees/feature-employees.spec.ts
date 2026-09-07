import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { ConfirmationService } from 'primeng/api';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { FeatureEmployees } from './feature-employees';

describe('FeatureEmployees', () => {
  let component: FeatureEmployees;
  let fixture: ComponentFixture<FeatureEmployees>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureEmployees],
      providers: [ConfirmationService, { provide: PERMISSION_CHECKER, useValue: signal(null) }],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureEmployees);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
