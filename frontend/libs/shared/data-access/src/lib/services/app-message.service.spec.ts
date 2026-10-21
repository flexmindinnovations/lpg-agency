import { AppMessageService } from './app-message.service';

describe('AppMessageService', () => {
  let service: AppMessageService;
  let added: unknown[];
  let clears: number;

  beforeEach(() => {
    service = new AppMessageService();
    added = [];
    clears = 0;
    service.messageObserver.subscribe((m) => added.push(m));
    service.clearObserver.subscribe(() => clears++);
  });

  it('clears earlier toasts before showing a success', () => {
    service.add({ severity: 'error', detail: 'One or more fields failed validation.' });
    expect(clears).toBe(0);
    service.add({ severity: 'success', detail: 'Complaint raised.' });
    expect(clears).toBe(1);
    expect(added).toHaveLength(2);
  });

  it('does not clear for errors, warnings or keyed toasts', () => {
    service.add({ severity: 'error', detail: 'a' });
    service.add({ severity: 'warn', detail: 'b' });
    service.add({ severity: 'success', detail: 'c', key: 'inline' });
    expect(clears).toBe(0);
  });

  it('gives a toast without a life the standard lifetime for its severity', () => {
    service.add({ severity: 'error', detail: 'x' });
    service.add({ severity: 'info', detail: 'y', life: 1000 });
    service.add({ severity: 'warn', detail: 'z', sticky: true });
    expect(added).toEqual([
      { severity: 'error', detail: 'x', life: 6000 },
      { severity: 'info', detail: 'y', life: 1000 },
      { severity: 'warn', detail: 'z', sticky: true },
    ]);
  });
});
