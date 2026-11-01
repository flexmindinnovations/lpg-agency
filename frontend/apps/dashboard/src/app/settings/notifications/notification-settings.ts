import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { Message } from 'primeng/message';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { MessageService } from 'primeng/api';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { PageHeaderComponent, SectionCardComponent } from '@lpg/shared/ui';
import {
  NotificationSettingsService,
  type NotificationEventResponse,
} from '@lpg/shared/data-access';

type Channel = 'in_app' | 'push' | 'sms' | 'email';

interface EventGroup {
  readonly heading: string;
  readonly events: readonly NotificationEventResponse[];
}

const AUDIENCES: readonly { key: string; heading: string }[] = [
  { key: 'customer', heading: 'Customer app' },
  { key: 'driver', heading: 'Driver app' },
  { key: 'staff', heading: 'Admin app and dashboard' },
];

/**
 * Which alert each system event sends, and on which channels (ADR-068). The
 * catalogue's defaults apply until an agency changes a switch. Who receives a
 * staff alert still follows their role's permissions. Critical events always
 * show in the app, and SMS/email are offered only where a template exists.
 */
@Component({
  selector: 'lpg-notification-settings',
  standalone: true,
  imports: [
    FormsModule,
    ButtonDirective,
    Message,
    ToggleSwitch,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    SectionCardComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ng-template lpgHeaderTitlePortal>
      <lpg-page-header
        title="Notifications"
        subtitle="Choose what each event tells customers, drivers and staff, and where."
      />
    </ng-template>

    <div class="notif">
      <p-message severity="info">
        Changes apply to new events straight away. Staff alerts go to people whose role allows the
        action; change that under Users &amp; roles. Alerts marked <em>Always on</em> keep their
        in-app message so nothing important can be missed. Delivery codes are not affected.
      </p-message>

      @for (audience of audiences(); track audience.heading) {
        <lpg-section-card [heading]="audience.heading" class="notif__card">
          @for (group of audience.groups; track group.heading) {
            <h3 class="notif__group">{{ group.heading }}</h3>
            <div class="notif__table" role="table" [attr.aria-label]="group.heading">
              <div class="notif__row notif__row--head" role="row">
                <span role="columnheader">Event</span>
                <span role="columnheader">In app</span>
                <span role="columnheader">Push</span>
                <span role="columnheader">SMS</span>
                <span role="columnheader">Email</span>
                <span role="columnheader"></span>
              </div>
              @for (event of group.events; track event.notification_type) {
                <div class="notif__row" role="row">
                  <span class="notif__name" role="cell">
                    <strong>{{ event.title }}</strong>
                    <small>{{ event.description }}</small>
                  </span>
                  @for (channel of channels; track channel.key) {
                    <span class="notif__cell" role="cell" [attr.data-label]="channel.label">
                      @if (event[channel.key].available) {
                        <p-toggleswitch
                          [ngModel]="event[channel.key].enabled"
                          [disabled]="
                            event[channel.key].locked || busy() === event.notification_type
                          "
                          [ariaLabel]="channel.label + ' for ' + event.title"
                          (onChange)="toggle(event, channel.key, $event.checked)"
                        />
                        @if (event[channel.key].locked) {
                          <small>Always on</small>
                        }
                      } @else {
                        <small class="notif__na" title="No approved template for this channel"
                          >—</small
                        >
                      }
                    </span>
                  }
                  <span class="notif__reset" role="cell">
                    @if (event.customized) {
                      <button
                        pButton
                        type="button"
                        size="small"
                        severity="secondary"
                        [text]="true"
                        [disabled]="busy() === event.notification_type"
                        (click)="reset(event)"
                      >
                        Reset
                      </button>
                    }
                  </span>
                </div>
              }
            </div>
          }
        </lpg-section-card>
      }
    </div>
  `,
  styles: [
    `
      .notif {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding-block-end: var(--spacing-xl);
      }
      .notif__card {
        inline-size: 100%;
        max-inline-size: none;
      }
      .notif__group {
        margin: var(--spacing-md) 0 var(--spacing-xs);
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .notif__row {
        display: grid;
        grid-template-columns: minmax(10rem, 1fr) repeat(4, 4.25rem) 4rem;
        align-items: center;
        gap: var(--spacing-sm);
        padding-block: var(--spacing-sm);
        border-block-end: 1px solid var(--color-border);
      }
      .notif__row--head {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-secondary);
      }
      .notif__name {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .notif__name small,
      .notif__cell small {
        color: var(--color-text-secondary);
      }
      .notif__cell {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .notif__table {
        container-type: inline-size;
      }
      @container (max-width: 38rem) {
        .notif__row--head {
          display: none;
        }
        .notif__name {
          grid-column: 1 / -1;
        }
        .notif__row {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .notif__cell::before {
          content: attr(data-label);
          font-size: var(--typography-body-small-font-size);
          color: var(--color-text-secondary);
        }
      }
    `,
  ],
})
export class NotificationSettings implements OnInit {
  private readonly service = inject(NotificationSettingsService);
  private readonly messages = inject(MessageService);

  protected readonly channels: readonly { key: Channel; label: string }[] = [
    { key: 'in_app', label: 'In app' },
    { key: 'push', label: 'Push' },
    { key: 'sms', label: 'SMS' },
    { key: 'email', label: 'Email' },
  ];

  protected readonly events = signal<NotificationEventResponse[]>([]);
  /** The event whose change is being saved. */
  protected readonly busy = signal<string | null>(null);

  protected readonly audiences = computed(() =>
    AUDIENCES.map(({ key, heading }) => {
      const mine = this.events().filter((e) => e.audience === key);
      const headings = [...new Set(mine.map((e) => e.group))];
      return {
        heading,
        groups: headings.map<EventGroup>((h) => ({
          heading: h,
          events: mine.filter((e) => e.group === h),
        })),
      };
    }).filter((a) => a.groups.length > 0),
  );

  ngOnInit(): void {
    this.service.list().subscribe({ next: (events) => this.events.set(events) });
  }

  protected toggle(event: NotificationEventResponse, channel: Channel, enabled: boolean): void {
    const body = {
      in_app: event.in_app.enabled,
      push: event.push.enabled,
      sms: event.sms.enabled,
      email: event.email.enabled,
      [channel]: enabled,
    };
    this.busy.set(event.notification_type);
    this.service.save(event.notification_type, body).subscribe({
      next: (saved) => this.replace(saved),
      // Put the switch back to what the server still has.
      error: () => {
        this.busy.set(null);
        this.events.update((all) => [...all]);
      },
    });
  }

  protected reset(event: NotificationEventResponse): void {
    this.busy.set(event.notification_type);
    this.service.reset(event.notification_type).subscribe({
      next: (saved) => {
        this.replace(saved);
        this.messages.add({ severity: 'success', summary: 'Back to the default' });
      },
      error: () => this.busy.set(null),
    });
  }

  private replace(saved: NotificationEventResponse): void {
    this.busy.set(null);
    this.events.update((all) =>
      all.map((e) => (e.notification_type === saved.notification_type ? saved : e)),
    );
  }
}
