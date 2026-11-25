import { TestBed } from '@angular/core/testing';
import { InfoTipComponent } from './info-tip.component';

describe('InfoTipComponent', () => {
  function render() {
    const fixture = TestBed.createComponent(InfoTipComponent);
    fixture.componentRef.setInput('text', 'Oil marketing company');
    document.body.appendChild(fixture.nativeElement);
    fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    const send = (target: EventTarget, event: Event) => {
      target.dispatchEvent(event);
      fixture.detectChanges();
    };
    const pointer = (type: string, pointerType: string) =>
      // jsdom has no PointerEvent.
      Object.assign(new Event(type, { bubbles: true }), { pointerType });
    /** The events a finger produces, in browser order. */
    const tap = () => {
      send(button, pointer('pointerenter', 'touch'));
      send(button, pointer('pointerdown', 'touch'));
      send(button, new Event('focus'));
      send(button, pointer('pointerleave', 'touch'));
      send(button, new MouseEvent('click', { bubbles: true }));
    };
    return { fixture, button, send, pointer, tap };
  }

  const tooltipText = () => document.querySelector('.p-tooltip-text')?.textContent ?? null;
  const expanded = (button: HTMLButtonElement) => button.getAttribute('aria-expanded');

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('is a button named by its explanation, with no native title', () => {
    const { fixture, button } = render();

    expect(button.type).toBe('button');
    expect(button.getAttribute('aria-label')).toBe('Oil marketing company');
    expect(fixture.nativeElement.querySelector('[title]')).toBeNull();
    expect(fixture.nativeElement.hasAttribute('title')).toBe(false);
  });

  it('stays open after a tap, and a second tap closes it', () => {
    const { button, tap } = render();

    tap();
    expect(tooltipText()).toBe('Oil marketing company');
    expect(expanded(button)).toBe('true');

    tap();
    expect(tooltipText()).toBeNull();
    expect(expanded(button)).toBe('false');
  });

  it('closes when the user presses somewhere else', () => {
    const { button, send, pointer, tap } = render();
    tap();

    send(document.body, pointer('pointerdown', 'touch'));

    expect(tooltipText()).toBeNull();
    expect(expanded(button)).toBe('false');
  });

  it('opens again with one tap after a scroll closed it', () => {
    const { button, send, tap } = render();
    tap();

    send(document, new Event('scroll'));
    expect(tooltipText()).toBeNull();

    tap();
    expect(tooltipText()).toBe('Oil marketing company');
    expect(expanded(button)).toBe('true');
  });

  it('follows the mouse until clicked, then stays', () => {
    const { button, send, pointer } = render();

    send(button, pointer('pointerenter', 'mouse'));
    expect(tooltipText()).toBe('Oil marketing company');
    send(button, pointer('pointerleave', 'mouse'));
    expect(tooltipText()).toBeNull();

    send(button, pointer('pointerenter', 'mouse'));
    send(button, new MouseEvent('click', { bubbles: true }));
    send(button, pointer('pointerleave', 'mouse'));
    expect(tooltipText()).toBe('Oil marketing company');
  });

  it('shows on keyboard focus and hides on Escape and on blur', () => {
    const { button, send } = render();

    send(button, new Event('focus'));
    expect(tooltipText()).toBe('Oil marketing company');
    send(button, new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(tooltipText()).toBeNull();

    send(button, new Event('focus'));
    send(button, new Event('blur'));
    expect(tooltipText()).toBeNull();
  });

  it('keeps its click and its Escape from the surrounding row or drawer', () => {
    const { fixture, button, send, tap } = render();
    const clicks = jest.fn();
    const keys = jest.fn();
    document.body.addEventListener('click', clicks);
    document.body.addEventListener('keydown', keys);

    tap();
    send(button, new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));

    expect(clicks).not.toHaveBeenCalled();
    expect(keys).not.toHaveBeenCalled();
    document.body.removeEventListener('click', clicks);
    document.body.removeEventListener('keydown', keys);
    fixture.destroy();
  });

  it('removes the tooltip when the component goes away', () => {
    const { fixture, tap } = render();
    tap();

    fixture.destroy();

    expect(tooltipText()).toBeNull();
  });
});
