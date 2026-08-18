import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ApiConfiguration } from '@lpg/shared/data-access';
import { NotificationDrawer } from './notification-drawer';

describe('NotificationDrawer', () => {
  let component: NotificationDrawer;
  let fixture: ComponentFixture<NotificationDrawer>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotificationDrawer],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NotificationDrawer);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
