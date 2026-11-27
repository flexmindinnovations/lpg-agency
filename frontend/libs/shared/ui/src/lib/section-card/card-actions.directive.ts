import {
  Directive,
  inject,
  type OnDestroy,
  type OnInit,
  TemplateRef,
  ViewContainerRef,
} from '@angular/core';
import { SectionCardComponent } from './section-card.component';

/**
 * Puts a child component's buttons on the heading line of the section card
 * around it. A card's own template uses the `headerActions` slot; a component
 * rendered inside the card cannot reach that slot, and uses this instead.
 *
 * ```html
 * <ng-template lpgCardActions>
 *   <button pButton (click)="add()"><i class="pi pi-plus"></i><span>Add</span></button>
 * </ng-template>
 * ```
 *
 * Outside a card the template renders where it is written.
 */
@Directive({
  selector: 'ng-template[lpgCardActions]',
  standalone: true,
})
export class CardActionsDirective implements OnInit, OnDestroy {
  private readonly template = inject<TemplateRef<unknown>>(TemplateRef);
  private readonly viewContainer = inject(ViewContainerRef);
  private readonly card = inject(SectionCardComponent, { optional: true });

  ngOnInit(): void {
    if (this.card) this.card.addActions(this.template);
    else this.viewContainer.createEmbeddedView(this.template);
  }

  ngOnDestroy(): void {
    this.card?.removeActions(this.template);
  }
}
