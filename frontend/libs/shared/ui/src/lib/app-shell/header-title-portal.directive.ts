import { Directive, inject, OnDestroy, OnInit, TemplateRef, ViewContainerRef } from '@angular/core';
import { TemplatePortal } from '@angular/cdk/portal';
import { HeaderPortalService } from './header-portal.service';

/**
 * Directive to register a template as the header title portal content.
 * Apply this directive to an <ng-template> in a feature page to project
 * its content into the application shell's top header.
 */
@Directive({
  selector: '[lpgHeaderTitlePortal]',
  standalone: true,
})
export class HeaderTitlePortalDirective implements OnInit, OnDestroy {
  private readonly templateRef = inject(TemplateRef);
  private readonly viewContainerRef = inject(ViewContainerRef);
  private readonly headerPortalService = inject(HeaderPortalService);

  private portal: TemplatePortal | null = null;

  ngOnInit(): void {
    this.portal = new TemplatePortal(this.templateRef, this.viewContainerRef);
    this.headerPortalService.titlePortal.set(this.portal);
  }

  ngOnDestroy(): void {
    if (this.headerPortalService.titlePortal() === this.portal) {
      this.headerPortalService.titlePortal.set(null);
    }
  }
}
