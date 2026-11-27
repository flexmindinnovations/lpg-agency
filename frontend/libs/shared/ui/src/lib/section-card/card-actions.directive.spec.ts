import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { CardActionsDirective } from './card-actions.directive';
import { SectionCardComponent } from './section-card.component';

/** A component rendered inside a card, which cannot reach the card's slot. */
@Component({
  selector: 'lpg-child-with-button',
  standalone: true,
  imports: [CardActionsDirective],
  template: `
    <ng-template lpgCardActions>
      @if (adding()) {
        <span class="adding">Adding</span>
      } @else {
        <button type="button" class="add" (click)="adding.set(true)">Add document</button>
      }
    </ng-template>
    <p class="content">Documents</p>
  `,
})
class ChildComponent {
  readonly adding = signal(false);
}

@Component({
  standalone: true,
  imports: [SectionCardComponent, ChildComponent],
  template: `
    <lpg-section-card [heading]="heading()">
      @if (shown()) {
        <lpg-child-with-button />
      }
    </lpg-section-card>
  `,
})
class CardHostComponent {
  readonly heading = signal('Compliance Documents');
  readonly shown = signal(true);
}

describe('CardActionsDirective', () => {
  async function render() {
    const fixture = TestBed.createComponent(CardHostComponent);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    return { fixture, el };
  }

  it("puts a child component's button on the card's heading line", async () => {
    const { el } = await render();

    expect(el.querySelector('.section-card__header .add')).not.toBeNull();
    expect(el.querySelector('.section-card__body .add')).toBeNull();
    expect(el.querySelectorAll('.add')).toHaveLength(1);
  });

  it('keeps the button working and following the child', async () => {
    const { fixture, el } = await render();

    el.querySelector<HTMLButtonElement>('.add')?.click();
    await fixture.whenStable();

    expect(el.querySelector('.section-card__header .adding')).not.toBeNull();
    expect(el.querySelector('.add')).toBeNull();
  });

  it('takes the button away with the child', async () => {
    const { fixture, el } = await render();

    fixture.componentInstance.shown.set(false);
    await fixture.whenStable();

    expect(el.querySelector('.add')).toBeNull();
  });

  it('gives a card without a heading a heading line for the button', async () => {
    const { fixture, el } = await render();

    fixture.componentInstance.heading.set('');
    await fixture.whenStable();

    expect(el.querySelector('.section-card__header .add')).not.toBeNull();
  });

  it('renders where it is written when there is no card', async () => {
    const fixture = TestBed.createComponent(ChildComponent);
    await fixture.whenStable();

    expect(fixture.nativeElement.querySelector('.add')).not.toBeNull();
  });
});
