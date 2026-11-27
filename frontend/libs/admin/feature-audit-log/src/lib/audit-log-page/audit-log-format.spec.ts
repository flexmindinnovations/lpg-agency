import type { AuditLogEntryResponse } from '@lpg/shared/data-access';
import {
  ACTION_LABELS,
  actorLabel,
  auditChanges,
  auditLogCsv,
  hasEarlierValues,
  orderIdForEntry,
  recordLabel,
  technicalIdentifiersOf,
} from './audit-log-format';

function entry(overrides: Partial<AuditLogEntryResponse>): AuditLogEntryResponse {
  return {
    id: 'log-1',
    actor_id: 'user-1',
    actor_display_name: 'admin@agency.in',
    entity_name: 'order',
    entity_id: 'cfa07245-0000-4000-8000-000000000000',
    entity_display_name: 'ORD000027',
    action: 'update',
    performed_at: '2026-10-20T04:39:00Z',
    correlation_id: null,
    before_state: null,
    after_state: null,
    ...overrides,
  };
}

describe('audit log formatting', () => {
  it('names the record, never the raw id', () => {
    expect(recordLabel(entry({}))).toBe('ORD000027');
    expect(
      recordLabel(entry({ entity_display_name: null, entity_name: 'order_status_history' })),
    ).toBe('Order Status History');
  });

  it('has words for every action the server records besides sign-in events', () => {
    const recorded = [
      'create',
      'update',
      'delete',
      'deactivate',
      'reactivate',
      'password_change',
      'platform.agency_admin_added',
      'platform.setup_link_issued',
      'device.registered',
      'device.named',
      'device.updated',
      'device.approved',
      'device.blocked',
      'device.unblocked',
      'device.removed',
      'device.deleted',
    ];

    expect(recorded.filter((action) => !ACTION_LABELS[action])).toEqual([]);
  });

  it('shows who did it, or System for background jobs', () => {
    expect(actorLabel(entry({}))).toBe('admin@agency.in');
    expect(actorLabel(entry({ actor_id: null, actor_display_name: null }))).toBe('System');
  });

  it('lists only changed fields for an update, without bookkeeping columns', () => {
    const changes = auditChanges(
      entry({
        before_state: { status: 'booked', version: 1 },
        after_state: { status: 'confirmed', version: 2, order_number: 'ORD000027' },
      }),
    );
    expect(changes).toEqual([{ field: 'Status', before: 'Booked', after: 'Confirmed' }]);
  });

  it('shows a "Before" column only when there is an earlier value', () => {
    const signIn = auditChanges(
      entry({ action: 'auth.login', after_state: { client_ip: '192.0.2.1', user_agent: 'x' } }),
    );
    const edit = auditChanges(
      entry({ before_state: { status: 'booked' }, after_state: { status: 'confirmed' } }),
    );

    expect(signIn.map((change) => change.field)).toEqual(['IP address', 'Browser or app']);
    expect(hasEarlierValues(signIn)).toBe(false);
    expect(hasEarlierValues(edit)).toBe(true);
  });

  it('lists the created values for a create', () => {
    const changes = auditChanges(
      entry({ action: 'create', after_state: { name: 'Nashik West', is_active: true } }),
    );
    expect(changes).toEqual([
      { field: 'Name', before: '', after: 'Nashik West' },
      { field: 'Is active', before: '', after: 'Yes' },
    ]);
  });

  it('extracts technical identifiers including ids from payload', () => {
    const ids = technicalIdentifiersOf(
      entry({
        id: 'log-1',
        entity_id: 'order-uuid-1',
        actor_id: 'actor-uuid-1',
        correlation_id: 'corr-1',
        after_state: { route_id: 'route-uuid-1', order_id: 'order-uuid-1' },
      }),
    );
    const keys = ids.map((i) => i.key);
    expect(keys).toContain('record_id');
    expect(keys).toContain('user_id');
    expect(keys).toContain('correlation_id');
    expect(keys).toContain('log_id');
    expect(keys).toContain('route_id');
    expect(keys).toContain('order_id');
  });

  it('resolves order id for navigation', () => {
    expect(orderIdForEntry(entry({ entity_name: 'orders', entity_id: 'order-uuid-1' }))).toBe(
      'order-uuid-1',
    );
    expect(
      orderIdForEntry(
        entry({
          entity_name: 'order_status_history',
          after_state: { order_id: 'order-uuid-from-history' },
        }),
      ),
    ).toBe('order-uuid-from-history');
  });

  it('exports the grid columns as CSV, quoting where needed', () => {
    const csv = auditLogCsv([entry({ entity_display_name: 'Iyer, Meena' })]);
    expect(csv).toBe(
      'When,Record,Record type,Action,Done by\r\n' +
        '"20 Oct 2026, 10:09","Iyer, Meena",Order,Changed,admin@agency.in',
    );
  });
});
