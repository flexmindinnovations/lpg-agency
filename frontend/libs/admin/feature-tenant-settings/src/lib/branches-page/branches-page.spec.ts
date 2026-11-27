import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ConfirmationService, type Confirmation } from 'primeng/api';
import { of } from 'rxjs';
import { AdminBranchService, NotifyService } from '@lpg/shared/data-access';
import { StatusChipCell, type RowAction } from '@lpg/shared/ui';
import { BranchesPage } from './branches-page';

const ACTIVE = { id: 'b1', name: 'Kukatpally', region: null, is_active: true };
const INACTIVE = { id: 'b2', name: 'Old Town', region: null, is_active: false };

describe('BranchesPage', () => {
  let branchService: Record<string, jest.Mock>;
  let confirmations: Confirmation[];

  function render() {
    confirmations = [];
    branchService = {
      listBranches: jest.fn().mockReturnValue(of([ACTIVE, INACTIVE])),
      setActive: jest.fn().mockReturnValue(of(undefined)),
      createBranch: jest.fn().mockReturnValue(of(ACTIVE)),
    };
    TestBed.configureTestingModule({
      imports: [BranchesPage],
      providers: [
        provideNoopAnimations(),
        { provide: AdminBranchService, useValue: branchService },
        { provide: NotifyService, useValue: { success: jest.fn(), error: jest.fn() } },
        {
          provide: ConfirmationService,
          useValue: { confirm: (c: Confirmation) => confirmations.push(c) },
        },
      ],
    });
    const fixture = TestBed.createComponent(BranchesPage);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  it('asks before deactivating a branch', () => {
    const page = render();

    page['toggleActive'](ACTIVE as never);
    expect(branchService['setActive']).not.toHaveBeenCalled();
    confirmations[0].accept?.();

    expect(branchService['setActive']).toHaveBeenCalledWith('b1', false);
  });

  it('reactivates without asking', () => {
    const page = render();

    page['toggleActive'](INACTIVE as never);

    expect(confirmations).toHaveLength(0);
    expect(branchService['setActive']).toHaveBeenCalledWith('b2', true);
  });

  it('shows the status as a chip and offers one button that matches it', () => {
    const page = render();
    const columns = page['columns'];
    const status = columns.find((c) => c.field === 'is_active');
    const [toggle] = columns.find((c) => c.header === 'Actions')?.cellRendererParams?.[
      'actions'
    ] as RowAction<typeof ACTIVE>[];
    const words = (row: typeof ACTIVE) =>
      typeof toggle.text === 'function' ? toggle.text(row) : toggle.text;

    expect(status?.cellRenderer).toBe(StatusChipCell);
    expect(words(ACTIVE)).toBe('Deactivate');
    expect(words(INACTIVE)).toBe('Activate');
    expect(toggle.label(ACTIVE)).toBe('Deactivate Kukatpally');
    toggle.onAction(INACTIVE);
    expect(branchService['setActive']).toHaveBeenCalledWith('b2', true);
  });

  it('rejects a whitespace-only name', () => {
    const page = render();

    page['form'].controls.name.setValue('   ');

    expect(page['form'].controls.name.hasError('required')).toBe(true);
  });
});
