import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MessageService } from 'primeng/api';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { NotificationFeatureNotifications } from './notification-feature-notifications';

describe('NotificationFeatureNotifications', () => {
  let component: NotificationFeatureNotifications;
  let fixture: ComponentFixture<NotificationFeatureNotifications>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotificationFeatureNotifications],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        MessageService,
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NotificationFeatureNotifications);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
