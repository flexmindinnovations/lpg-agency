import { TestBed } from '@angular/core/testing';
import { KeyboardShortcutsService } from './keyboard-shortcuts.service';

function dispatchKey(
  key: string,
  opts: { ctrl?: boolean; shift?: boolean; alt?: boolean; target?: EventTarget } = {},
): KeyboardEvent {
  const event = new KeyboardEvent('keydown', {
    key,
    ctrlKey: !!opts.ctrl,
    shiftKey: !!opts.shift,
    altKey: !!opts.alt,
    bubbles: true,
    cancelable: true,
  });
  Object.defineProperty(event, 'target', { value: opts.target ?? document.body });
  document.dispatchEvent(event);
  return event;
}

describe('KeyboardShortcutsService', () => {
  let service: KeyboardShortcutsService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(KeyboardShortcutsService);
  });

  it('invokes the correct handler on an exact match', () => {
    const handler = jest.fn();
    service.register({ key: 'k', ctrl: true, description: 'Search', handler });

    dispatchKey('k', { ctrl: true });

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('accepts metaKey as equivalent to ctrl (Cmd on macOS)', () => {
    const handler = jest.fn();
    service.register({ key: 'k', ctrl: true, description: 'Search', handler });

    const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true });
    Object.defineProperty(event, 'target', { value: document.body });
    document.dispatchEvent(event);

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not fire when a required modifier is missing', () => {
    const handler = jest.fn();
    service.register({ key: 'k', ctrl: true, description: 'Search', handler });

    dispatchKey('k'); // no ctrl

    expect(handler).not.toHaveBeenCalled();
  });

  it('does not fire when an extra modifier is present', () => {
    const handler = jest.fn();
    service.register({ key: 'k', description: 'Something', handler });

    dispatchKey('k', { shift: true }); // binding has no shift

    expect(handler).not.toHaveBeenCalled();
  });

  it('matches case-insensitively against the registered key', () => {
    const handler = jest.fn();
    service.register({ key: 'k', description: 'Search', handler });

    const event = new KeyboardEvent('keydown', { key: 'K', bubbles: true });
    Object.defineProperty(event, 'target', { value: document.body });
    document.dispatchEvent(event);

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('never hijacks typing in an input field', () => {
    const handler = jest.fn();
    service.register({ key: 'n', description: 'New', handler });
    const input = document.createElement('input');

    dispatchKey('n', { target: input });

    expect(handler).not.toHaveBeenCalled();
  });

  it('never hijacks typing in a textarea or select', () => {
    const handler = jest.fn();
    service.register({ key: 'n', description: 'New', handler });

    dispatchKey('n', { target: document.createElement('textarea') });
    dispatchKey('n', { target: document.createElement('select') });

    expect(handler).not.toHaveBeenCalled();
  });

  it('never hijacks typing in a contenteditable element', () => {
    const handler = jest.fn();
    service.register({ key: 'n', description: 'New', handler });
    const div = document.createElement('div');
    Object.defineProperty(div, 'isContentEditable', { value: true });

    dispatchKey('n', { target: div });

    expect(handler).not.toHaveBeenCalled();
  });

  it('makes an exception for Escape even while focused in a field', () => {
    // Closing a dialog from inside a focused field is exactly what a user
    // expects — the one case where hijacking typing is correct.
    const handler = jest.fn();
    service.register({ key: 'escape', description: 'Close', handler });
    const input = document.createElement('input');

    dispatchKey('escape', { target: input });

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('calls preventDefault only when a binding actually matches', () => {
    service.register({ key: 'k', ctrl: true, description: 'Search', handler: jest.fn() });

    const matched = dispatchKey('k', { ctrl: true });
    const unmatched = dispatchKey('x');

    expect(matched.defaultPrevented).toBe(true);
    expect(unmatched.defaultPrevented).toBe(false);
  });

  it('unregister stops the binding from firing', () => {
    const handler = jest.fn();
    const unregister = service.register({ key: 'k', description: 'Search', handler });

    unregister();
    dispatchKey('k');

    expect(handler).not.toHaveBeenCalled();
  });

  it('exposes registered bindings for a shortcuts help dialog', () => {
    expect(service.registered()).toHaveLength(0);

    const unregister = service.register({ key: 'k', description: 'Search', handler: jest.fn() });
    expect(service.registered()).toHaveLength(1);
    expect(service.registered()[0].description).toBe('Search');

    unregister();
    expect(service.registered()).toHaveLength(0);
  });

  it('supports multiple simultaneous bindings without cross-firing', () => {
    const search = jest.fn();
    const create = jest.fn();
    service.register({ key: 'k', ctrl: true, description: 'Search', handler: search });
    service.register({ key: 'n', ctrl: true, description: 'New', handler: create });

    dispatchKey('n', { ctrl: true });

    expect(create).toHaveBeenCalledTimes(1);
    expect(search).not.toHaveBeenCalled();
  });
});
