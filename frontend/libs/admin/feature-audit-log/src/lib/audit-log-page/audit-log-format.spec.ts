import type { AuditLogEntryResponse } from '@lpg/shared/data-access';
import { actorLabel, auditChanges, auditLogCsv, recordLabel } from './audit-log-format';

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
    expect(recordLabel(entry({ entity_display_name: null, entity_name: 'order_status_history' })))
      .toBe('Order Status History');
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
    expect(changes).toEqual([{ field: 'Status', before: 'booked', after: 'confirmed' }]);
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

  it('exports the grid columns as CSV, quoting where needed', () => {
    const csv = auditLogCsv([entry({ entity_display_name: 'Iyer, Meena' })]);
    expect(csv).toBe(
      'When,Record,Record type,Action,Done by\r\n' +
        '"20 Oct 2026, 10:09","Iyer, Meena",Order,Changed,admin@agency.in',
    );
  });
});
