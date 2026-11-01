import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { MessageService } from 'primeng/api';
import { NotificationSettingsService } from '@lpg/shared/data-access';
import { NotificationSettings } from './notification-settings';

const channel = (enabled: boolean, extra: object = {}) => ({
  enabled,
  default: enabled,
  available: true,
  locked: false,
  ...extra,
});

const event = (type: string, audience: string, extra: object = {}) => ({
  notification_type: type,
  title: type,
  description: `${type} description`,
  audience,
  group: 'Orders',
  critical: false,
  customized: false,
  in_app: channel(true),
  push: channel(true),
  sms: channel(false, { available: false }),
  email: channel(false, { available: false }),
  ...extra,
});

describe('NotificationSettings', () => {
  function create(events: object[]) {
    const service = {
      list: jest.fn(() => of(events)),
      save: jest.fn((type: string, body: Record<string, boolean>) =>
        of(
          event(type, 'staff', {
            customized: true,
            push: channel(body['push']),
          }),
        ),
      ),
      reset: jest.fn((type: string) => of(event(type, 'staff'))),
    };
    TestBed.configureTestingModule({
      imports: [NotificationSettings],
      providers: [{ provide: NotificationSettingsService, useValue: service }, MessageService],
    });
    const fixture = TestBed.createComponent(NotificationSettings);
    fixture.detectChanges();
    return { fixture, service, el: fixture.nativeElement as HTMLElement };
  }

  it('groups events by the app that receives them', () => {
    const { el } = create([event('a', 'customer'), event('b', 'staff')]);
    const headings = (el.querySelectorAll('lpg-section-card') as NodeListOf<HTMLElement>).length;
    expect(headings).toBe(2);
  });

  it('saves the whole row with the one channel that changed', () => {
    const { fixture, service } = create([event('order_placed_staff', 'staff')]);
    (
      fixture.componentInstance as unknown as {
        toggle(e: object, c: string, on: boolean): void;
      }
    ).toggle(event('order_placed_staff', 'staff'), 'push', false);
    expect(service.save).toHaveBeenCalledWith('order_placed_staff', {
      in_app: true,
      push: false,
      sms: false,
      email: false,
    });
  });

  it('offers a reset only for customised events', () => {
    const { el } = create([event('a', 'staff', { customized: true }), event('b', 'staff')]);
    expect(el.querySelectorAll('.notif__reset button')).toHaveLength(1);
  });

  it('hides SMS and email where there is no template', () => {
    const { el } = create([event('a', 'staff')]);
    expect(el.querySelectorAll('p-toggleswitch')).toHaveLength(2);
  });
});
