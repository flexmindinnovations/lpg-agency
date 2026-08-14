import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NotificationFeatureNotifications } from './notification-feature-notifications';

describe('NotificationFeatureNotifications', () => {
  let component: NotificationFeatureNotifications;
  let fixture: ComponentFixture<NotificationFeatureNotifications>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotificationFeatureNotifications]
    }).compileComponents();

    fixture = TestBed.createComponent(NotificationFeatureNotifications);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
