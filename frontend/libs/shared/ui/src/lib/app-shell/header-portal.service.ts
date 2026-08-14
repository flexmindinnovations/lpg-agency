import { Injectable, signal } from '@angular/core';
import { TemplatePortal } from '@angular/cdk/portal';

/**
 * Service to manage the header portal, allowing feature pages to project
 * dynamic action buttons into the application shell's global header.
 */
@Injectable({ providedIn: 'root' })
export class HeaderPortalService {
  readonly portal = signal<TemplatePortal | null>(null);
  readonly titlePortal = signal<TemplatePortal | null>(null);
}
