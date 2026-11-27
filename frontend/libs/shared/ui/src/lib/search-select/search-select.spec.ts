import { TestBed } from '@angular/core/testing';
import { FilterService } from 'primeng/api';
import { Subject } from 'rxjs';
import { SearchSelect } from './search-select';

interface Person {
  id: string;
  name: string;
  phone: string;
}

describe('SearchSelect', () => {
  type Internals = {
    ask: (query: string) => void;
    pick: (item: Person | null) => void;
    options: () => { label: string; detail: string; item: Person }[];
    searchBox: () => { pcFilter: { root: Record<string, string> } };
    loading: () => boolean;
    message: () => string;
    query: { set: (value: string) => void };
  };

  const ravi: Person = { id: '1', name: 'Ravi', phone: '98000' };
  const meena: Person = { id: '2', name: 'Meena', phone: '97000' };
  let asked: { query: string; answer: Subject<Person[]> }[];

  beforeEach(() => {
    jest.useFakeTimers();
    asked = [];
  });
  afterEach(() => jest.useRealTimers());

  function setup() {
    const fixture = TestBed.createComponent(SearchSelect<Person>);
    fixture.componentRef.setInput('inputId', 'person');
    fixture.componentRef.setInput('itemLabel', (p: Person) => p.name);
    fixture.componentRef.setInput('itemDetail', (p: Person) => p.phone);
    fixture.componentRef.setInput('noMatchMessage', 'No people match');
    fixture.componentRef.setInput('search', (query: string) => {
      const answer = new Subject<Person[]>();
      asked.push({ query, answer });
      return answer;
    });
    fixture.detectChanges();
    return { fixture, select: fixture.componentInstance as unknown as Internals };
  }

  const names = (select: Internals) => select.options().map((o) => o.label);

  it('is a searchable p-select like every other dropdown', () => {
    const { fixture } = setup();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('p-select')).not.toBeNull();
    expect(element.querySelector('p-autocomplete')).toBeNull();
  });

  it('says on its search box what it can search by', () => {
    const { fixture, select } = setup();

    fixture.componentRef.setInput('searchHint', 'Name or phone');

    expect(select.searchBox().pcFilter.root).toEqual({
      placeholder: 'Name or phone',
      'aria-label': 'Name or phone',
    });
  });

  it('lists the first entries at once when opened', () => {
    const { select } = setup();

    select.ask('');
    expect(asked.map((a) => a.query)).toEqual(['']);
    expect(select.loading()).toBe(true);
    expect(select.message()).toBe('Searching…');
    asked[0].answer.next([ravi, meena]);

    expect(names(select)).toEqual(['Ravi', 'Meena']);
    expect(select.options()[0].detail).toBe('98000');
    expect(select.loading()).toBe(false);
  });

  it('waits for a pause in typing, tidies the query and drops outdated answers', () => {
    const { select } = setup();

    select.ask('r');
    select.ask('  ravi   k ');
    expect(asked).toHaveLength(0);
    jest.advanceTimersByTime(300);
    expect(asked.map((a) => a.query)).toEqual(['ravi k']);

    select.ask('meena');
    jest.advanceTimersByTime(300);
    asked[1].answer.next([meena]);
    asked[0].answer.next([ravi]);

    expect(names(select)).toEqual(['Meena']);
  });

  it('keeps every server answer, whatever words matched on the server', () => {
    setup();

    const kept = TestBed.inject(FilterService).filter(
      [{ label: 'Ravi' }],
      ['label'],
      '98 000',
      'lpgServerMatch',
    );

    expect(kept).toHaveLength(1);
  });

  it('says when nothing matches and when the search fails', () => {
    const { select } = setup();

    select.ask('');
    asked[0].answer.next([]);
    expect(select.message()).toBe('No people match');

    select.ask('');
    asked[1].answer.error(new Error('offline'));
    expect(select.message()).toBe("Couldn't load the list. Try again.");

    // A failed search does not stop later ones.
    select.ask('');
    asked[2].answer.next([ravi]);
    expect(names(select)).toEqual(['Ravi']);
  });

  it('gives the form the picked item and keeps it listed after another search', () => {
    const { select } = setup();
    const changes: (Person | null)[] = [];
    (select as unknown as SearchSelect<Person>).registerOnChange((v) => changes.push(v));

    select.pick(ravi);
    select.ask('meena');
    jest.advanceTimersByTime(300);
    asked[0].answer.next([meena]);

    expect(changes).toEqual([ravi]);
    // While searching, only the matches are listed.
    expect(names(select)).toEqual(['Meena']);
    // Closed again, the picked one is back so its name still shows.
    select.query.set('');
    expect(names(select)).toEqual(['Ravi', 'Meena']);
  });

  it('shows a value set by the form, and clears with it', async () => {
    const { fixture, select } = setup();

    fixture.componentInstance.writeValue(ravi);
    fixture.detectChanges();
    // `ngModel` hands the value to the dropdown one microtask later.
    await Promise.resolve();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ravi');

    fixture.componentInstance.writeValue(null);
    expect(names(select)).toEqual([]);
  });
});
