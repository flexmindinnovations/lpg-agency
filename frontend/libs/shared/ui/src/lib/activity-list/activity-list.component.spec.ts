import { TestBed } from '@angular/core/testing';
import { ActivityListComponent, type ActivityItem } from './activity-list.component';

const ITEMS: ActivityItem[] = [
  { time: '2m ago', icon: 'pi pi-check', title: 'Order #ORD-1248', description: 'Delivered', status: 'Done', statusTone: 'success' },
  { time: '15m ago', icon: 'pi pi-wallet', title: 'Payment received', description: '₹45,000' },
];

describe('ActivityListComponent', () => {
  function render(items: ActivityItem[]) {
    const fixture = TestBed.createComponent(ActivityListComponent);
    fixture.componentRef.setInput('items', items);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders one row per item with its time and title', () => {
    const el = render(ITEMS);
    const rows = el.querySelectorAll('.activity-list__item');
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector('.activity-list__title')?.textContent).toContain('Order #ORD-1248');
    expect(rows[0].querySelector('.activity-list__time')?.textContent).toContain('2m ago');
  });

  it('renders a toned status chip only when a status is present', () => {
    const el = render(ITEMS);
    const chips = el.querySelectorAll('.activity-list__status');
    expect(chips).toHaveLength(1);
    expect(chips[0].className).toContain('activity-list__status--success');
  });
});
