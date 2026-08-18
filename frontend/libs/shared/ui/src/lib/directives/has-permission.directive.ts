import { Directive, Input, TemplateRef, ViewContainerRef, inject, effect } from '@angular/core';
import { PERMISSION_CHECKER } from '@lpg/shared/util';

@Directive({
  selector: '[lpgHasPermission]',
  standalone: true,
})
export class HasPermissionDirective {
  private templateRef = inject(TemplateRef<unknown>);
  private viewContainer = inject(ViewContainerRef);
  private permissionChecker = inject(PERMISSION_CHECKER);

  private permission: string | undefined | null = '';
  private hasView = false;

  @Input() set lpgHasPermission(permission: string | undefined | null) {
    this.permission = permission;
  }

  constructor() {
    effect(() => {
      // If no permission is required, grant access immediately
      if (!this.permission) {
        if (!this.hasView) {
          this.viewContainer.createEmbeddedView(this.templateRef);
          this.hasView = true;
        }
        return;
      }

      const state = this.permissionChecker();
      const hasPermission = state?.permissions?.has(this.permission) ?? false;

      if (hasPermission && !this.hasView) {
        this.viewContainer.createEmbeddedView(this.templateRef);
        this.hasView = true;
      } else if (!hasPermission && this.hasView) {
        this.viewContainer.clear();
        this.hasView = false;
      }
    });
  }
}
