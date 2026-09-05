import { Component, input } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { SectionCardComponent } from './section-card.component';

@Component({
  standalone: true,
  imports: [SectionCardComponent],
  template: `
    <lpg-section-card [heading]="heading()">
      <p class="projected">Body content</p>
    </lpg-section-card>
  `,
})
class HostComponent {
  readonly heading = input('');
}

describe('SectionCardComponent', () => {
  function render(heading: string) {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.componentRef.setInput('heading', heading);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders the heading and projects the body', () => {
    const el = render('Fleet Status');
    expect(el.querySelector('.section-card__heading')?.textContent).toContain('Fleet Status');
    expect(el.querySelector('.projected')?.textContent).toContain('Body content');
  });

  it('drops the header row when there is no heading and no header actions', () => {
    const el = render('');
    expect(el.querySelector('.section-card__header')).toBeNull();
    expect(el.querySelector('.projected')?.textContent).toContain('Body content');
  });
});
