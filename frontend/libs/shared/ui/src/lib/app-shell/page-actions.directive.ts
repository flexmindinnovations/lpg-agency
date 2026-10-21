import { Directive, inject, OnDestroy, OnInit, TemplateRef, ViewContainerRef } from '@angular/core';
import { TemplatePortal } from '@angular/cdk/portal';
import { HeaderPortalService } from './header-portal.service';

/**
 * Registers a template as the page's actions. The shell renders it on the
 * right of the breadcrumb row, so every page puts its buttons (New, Register,
 * Confirm, Cancel, ...) in the same place and needs no Back button: the
 * breadcrumb is the way back.
 *
 * ```html
 * <ng-template lpgPageActions>
 *   <button pButton (click)="openCreate()"><i class="pi pi-plus"></i><span>New</span></button>
 * </ng-template>
 * ```
 *
 * Filters, search and Export stay with the table they act on.
 */
@Directive({
  selector: '[lpgPageActions]',
  standalone: true,
})
export class PageActionsDirective implements OnInit, OnDestroy {
  private readonly templateRef = inject(TemplateRef);
  private readonly viewContainerRef = inject(ViewContainerRef);
  private readonly headerPortalService = inject(HeaderPortalService);

  private portal: TemplatePortal | null = null;

  ngOnInit(): void {
    this.portal = new TemplatePortal(this.templateRef, this.viewContainerRef);
    this.headerPortalService.actionsPortal.set(this.portal);
  }

  ngOnDestroy(): void {
    if (this.headerPortalService.actionsPortal() === this.portal) {
      this.headerPortalService.actionsPortal.set(null);
    }
  }
}
