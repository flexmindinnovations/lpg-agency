import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NotificationDrawer } from './notification-drawer';

describe('NotificationDrawer', () => {
  let component: NotificationDrawer;
  let fixture: ComponentFixture<NotificationDrawer>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotificationDrawer]
    }).compileComponents();

    fixture = TestBed.createComponent(NotificationDrawer);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
