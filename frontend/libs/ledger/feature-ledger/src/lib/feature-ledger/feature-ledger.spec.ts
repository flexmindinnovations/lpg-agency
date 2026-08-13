import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FeatureLedger } from './feature-ledger';

describe('FeatureLedger', () => {
  let component: FeatureLedger;
  let fixture: ComponentFixture<FeatureLedger>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureLedger],
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureLedger);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
