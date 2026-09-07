import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { FeatureComplaints } from './feature-complaints';

describe('FeatureComplaints', () => {
  let component: FeatureComplaints;
  let fixture: ComponentFixture<FeatureComplaints>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureComplaints],
      providers: [{ provide: PERMISSION_CHECKER, useValue: signal(null) }],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureComplaints);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
