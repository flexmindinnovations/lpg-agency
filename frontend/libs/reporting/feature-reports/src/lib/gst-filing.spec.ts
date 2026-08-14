import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GstFiling } from './gst-filing';

describe('GstFiling', () => {
  let component: GstFiling;
  let fixture: ComponentFixture<GstFiling>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GstFiling],
    }).compileComponents();

    fixture = TestBed.createComponent(GstFiling);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
