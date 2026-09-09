import { ChangeDetectionStrategy, Component, input, viewChild } from '@angular/core';
import { PreviewDialog } from '../preview-dialog/preview-dialog';

/** The subset of `BranchResponse` this component actually needs — kept
 *  local rather than imported from `@lpg/shared/data-access` so `shared/ui`
 *  stays free of a dependency on the generated API client. Any real
 *  `BranchResponse` already satisfies this shape. */
export interface BranchLinkBranch {
  name: string;
  region: string | null;
  is_active: boolean;
}

/**
 * Renders a branch as a link; clicking it opens a read-only "Branch
 * Details" quick-view via the shared `lpg-preview-dialog`. Falls back to
 * the raw `branchId` as plain text when `branch` doesn't resolve — e.g. a
 * cross-tenant or otherwise-bad id that the caller's own tenant-scoped
 * branch list can't find a name for. The caller does the id → branch
 * lookup itself (both call sites already load the tenant's branches for
 * exactly this purpose) — this component only renders the result.
 */
@Component({
  selector: 'lpg-branch-link',
  standalone: true,
  imports: [PreviewDialog],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (branch(); as b) {
      <button type="button" class="lpg-branch-link" (click)="openDetails(b)">{{ b.name }}</button>
      <lpg-preview-dialog #dialog header="Branch Details" />
    } @else {
      {{ branchId() }}
    }
  `,
  styles: [
    `
      .lpg-branch-link {
        background: none;
        border: none;
        padding: 0;
        margin: 0;
        font: inherit;
        color: var(--color-action-primary);
        text-decoration: underline;
        cursor: pointer;
      }

      .lpg-branch-link:hover {
        color: var(--color-action-primary-hover);
      }
    `,
  ],
})
export class BranchLinkComponent {
  readonly branchId = input.required<string>();
  readonly branch = input<BranchLinkBranch | null>(null);

  private readonly dialog = viewChild(PreviewDialog);

  protected openDetails(b: BranchLinkBranch): void {
    const dialog = this.dialog();
    if (!dialog) return;
    dialog.open();
    dialog.showData({
      title: b.name,
      tags: [
        b.is_active
          ? { label: 'Active', severity: 'success' }
          : { label: 'Inactive', severity: 'secondary' },
      ],
      fields: [{ label: 'Region', value: b.region ?? '—' }],
    });
  }
}
