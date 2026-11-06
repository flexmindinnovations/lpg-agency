import { TestBed } from '@angular/core/testing';
import { ToggleGroupComponent, type ToggleOption } from './toggle-group.component';

const OPTIONS: readonly ToggleOption[] = [
  { value: 'all', label: 'All', icon: 'pi pi-list' },
  { value: 'waiting', label: 'Waiting' },
  { value: 'blocked', label: 'Blocked' },
];

describe('ToggleGroupComponent', () => {
  function render(value = 'all', extra: Record<string, unknown> = {}) {
    const fixture = TestBed.createComponent(ToggleGroupComponent<string>);
    fixture.componentRef.setInput('options', OPTIONS);
    fixture.componentRef.setInput('value', value);
    fixture.componentRef.setInput('ariaLabel', 'Show phones by state');
    for (const [k, v] of Object.entries(extra)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(el.querySelectorAll('button'));
    return { fixture, el, buttons, component: fixture.componentInstance };
  }

  it('shows one button per option and names the group', () => {
    const { el, buttons } = render();

    expect(buttons.map((b) => b.textContent?.trim())).toEqual(['All', 'Waiting', 'Blocked']);
    expect(el.querySelector('[role="group"]')?.getAttribute('aria-label')).toBe(
      'Show phones by state',
    );
  });

  it('marks only the chosen option as pressed', () => {
    const { buttons } = render('waiting');

    expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual(['false', 'true', 'false']);
  });

  it('draws an icon only when the option has one', () => {
    const { buttons } = render();

    expect(buttons[0].querySelector('i.pi-list')).not.toBeNull();
    expect(buttons[1].querySelector('i')).toBeNull();
  });

  it('announces a different choice but does not change the value by itself', () => {
    const { component, buttons, fixture } = render('all');
    const picked: string[] = [];
    component.valueChange.subscribe((v) => picked.push(v));

    buttons[2].click();
    fixture.detectChanges();

    expect(picked).toEqual(['blocked']);
    expect(component.value()).toBe('all');
    expect(buttons[0].getAttribute('aria-pressed')).toBe('true');
  });

  it('stays quiet when the chosen option is clicked again', () => {
    const { component, buttons } = render('all');
    const picked: string[] = [];
    component.valueChange.subscribe((v) => picked.push(v));

    buttons[0].click();

    expect(picked).toEqual([]);
  });

  it('disables every button when disabled', () => {
    const { buttons } = render('all', { disabled: true });

    expect(buttons.every((b) => b.disabled)).toBe(true);
  });
});
