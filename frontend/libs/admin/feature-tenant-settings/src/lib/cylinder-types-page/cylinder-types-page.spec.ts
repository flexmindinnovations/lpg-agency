import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ConfirmationService, type Confirmation } from 'primeng/api';
import { of, throwError } from 'rxjs';
import {
  AdminBranchService,
  AdminCylinderTypeService,
  AdminPriceListService,
  AdminTenantConfigurationService,
  NotifyService,
  type CylinderTypeResponse,
  type PriceListEntryResponse,
  type CylinderTypeUsageResponse,
} from '@lpg/shared/data-access';
import { StatusChipCell, type RowAction } from '@lpg/shared/ui';
import { CylinderTypeDrawer } from './cylinder-type-drawer';
import { CylinderTypesPage } from './cylinder-types-page';
import { PriceDrawer } from './price-drawer';

const SIZES = [
  { code: 'domestic_5', name: '5 kg Domestic', category: 'domestic', weight_kg: '5' },
  { code: 'domestic_14_2', name: '14.2 kg Domestic', category: 'domestic', weight_kg: '14.2' },
  { code: 'commercial_19', name: '19 kg Commercial', category: 'commercial', weight_kg: '19' },
  { code: 'commercial_35', name: '35 kg Commercial', category: 'commercial', weight_kg: '35' },
];

const DOMESTIC: CylinderTypeResponse = {
  id: 'c1',
  name: '14.2 kg Domestic',
  weight_kg: '14.20',
  size_code: 'domestic_14_2',
  category: 'domestic',
  hsn_code: '27111900',
  gst_rate_percent: '5.00',
  is_active: true,
};
const TYPED_BY_HAND: CylinderTypeResponse = {
  id: 'c2',
  name: '19KG_Domestic',
  weight_kg: '19.00',
  size_code: null,
  category: null,
  hsn_code: null,
  gst_rate_percent: null,
  is_active: true,
};

const UNUSED: CylinderTypeUsageResponse = {
  used_in: [],
  delete_blocked_by: [],
  allowed_size_codes: SIZES.map((size) => size.code),
};
const USED: CylinderTypeUsageResponse = {
  used_in: ['stock records', 'prices'],
  delete_blocked_by: ['stock records'],
  allowed_size_codes: ['domestic_14_2'],
};

const PRICE: PriceListEntryResponse = {
  id: 'p1',
  cylinder_type_id: 'c1',
  customer_type: 'domestic',
  branch_id: null,
  price: '853.00',
  effective_from: '2026-01-01T00:00:00Z',
};

let service: Record<string, jest.Mock>;
let priceService: Record<string, jest.Mock>;
let notify: { success: jest.Mock; error: jest.Mock };
let confirmations: Confirmation[];

function setUp(
  types: CylinderTypeResponse[],
  usage: CylinderTypeUsageResponse,
  prices: PriceListEntryResponse[] = [PRICE],
  branches: { id: string; name: string; is_active: boolean }[] = [],
): void {
  confirmations = [];
  notify = { success: jest.fn(), error: jest.fn() };
  priceService = {
    listPrices: jest.fn().mockReturnValue(of(prices)),
    setPrice: jest.fn().mockReturnValue(of(PRICE)),
    listProposals: jest.fn().mockReturnValue(of([])),
    reviewProposal: jest.fn().mockReturnValue(of({})),
  };
  service = {
    listCylinderTypes: jest.fn().mockReturnValue(of(types)),
    listCylinderSizes: jest.fn().mockReturnValue(of(SIZES)),
    getUsage: jest.fn().mockReturnValue(of(usage)),
    createCylinderType: jest.fn().mockReturnValue(of(DOMESTIC)),
    updateCylinderType: jest.fn().mockReturnValue(of(DOMESTIC)),
    deleteCylinderType: jest.fn().mockReturnValue(of(undefined)),
    classifyForGst: jest.fn().mockReturnValue(of(DOMESTIC)),
    setActive: jest.fn().mockReturnValue(of(undefined)),
  };
  TestBed.configureTestingModule({
    providers: [
      provideNoopAnimations(),
      { provide: AdminCylinderTypeService, useValue: service },
      { provide: AdminPriceListService, useValue: priceService },
      { provide: AdminBranchService, useValue: { listBranches: () => of(branches) } },
      {
        provide: AdminTenantConfigurationService,
        useValue: { getEffectiveConfiguration: () => of(null) },
      },
      { provide: NotifyService, useValue: notify },
      {
        provide: ConfirmationService,
        useValue: { confirm: (c: Confirmation) => confirmations.push(c) },
      },
    ],
  });
}

describe('CylinderTypesPage', () => {
  function render(
    types: CylinderTypeResponse[] = [DOMESTIC],
    prices: PriceListEntryResponse[] = [PRICE],
  ) {
    setUp(types, UNUSED, prices);
    const fixture = TestBed.createComponent(CylinderTypesPage);
    fixture.detectChanges();
    return { fixture, page: fixture.componentInstance };
  }

  it('points out a cylinder on sale with an unusual GST rate', () => {
    const commercial = {
      ...DOMESTIC,
      id: 'c4',
      name: '19 kg Commercial',
      size_code: 'commercial_19',
      category: 'commercial',
    };

    const { fixture } = render([DOMESTIC, commercial]);

    const warnings = [...fixture.nativeElement.querySelectorAll('.gst-warning__item')].map((item) =>
      (item as HTMLElement).textContent?.replace(/\s+/g, ' ').trim(),
    );
    expect(warnings).toEqual([
      '19 kg Commercial: GST on commercial LPG is usually 18%, not 5%. Check with your accountant.',
    ]);
  });

  it('does not point out a cylinder that is no longer sold', () => {
    const { page } = render([{ ...DOMESTIC, category: 'commercial', is_active: false }]);

    expect(page['rateWarnings']()).toEqual([]);
  });

  it('warns while an unusual rate is typed for a new cylinder', () => {
    const { page } = render();

    page['form'].controls.category.setValue('commercial');
    expect(page['form'].controls.gstRatePercent.value).toBe(18);
    expect(page['newGstHint']()).not.toContain('accountant');

    page['form'].patchValue({ gstRatePercent: 5 });
    expect(page['newGstHint']()).toContain('usually 18%, not 5%');
  });

  const columnFields = (page: CylinderTypesPage) => page['columns'].map((column) => column.field);
  const column = (page: CylinderTypesPage, field: string) =>
    page['columns'].find((c) => c.field === field);
  type Row = ReturnType<CylinderTypesPage['rows']>[number];
  const listed = (page: CylinderTypesPage, id: string) => {
    const row = page['rows']().find((r) => r.id === id);
    if (!row) throw new Error(`no row ${id}`);
    return row;
  };
  /** The words on the buttons a row offers. */
  const buttons = (page: CylinderTypesPage, row: Row) =>
    (column(page, 'actions')?.cellRendererParams?.['actions'] as RowAction<Row>[])
      .filter((a) => a.visible?.(row) ?? true)
      .map((a) => (typeof a.text === 'function' ? a.text(row) : a.text));

  it('offers the sizes of the chosen type that are not added yet', () => {
    const { page } = render();
    const offered = () => page['sizesOfChosenType']().map((size) => size.code);

    expect(page['availableCategories']().map((option) => option.label)).toEqual([
      'Domestic',
      'Commercial and industrial',
    ]);
    expect(offered()).toEqual([]);
    expect(page['noOptionsMessage']()).toBe('Choose a cylinder type first.');
    page['form'].controls.category.setValue('domestic');
    expect(offered()).toEqual(['domestic_5']);
    page['form'].controls.category.setValue('commercial');
    expect(offered()).toEqual(['commercial_19', 'commercial_35']);
  });

  it('clears the size when the type changes', () => {
    const { page } = render();

    page['form'].controls.category.setValue('commercial');
    page['form'].controls.sizeCode.setValue('commercial_19');
    page['form'].controls.category.setValue('domestic');

    expect(page['form'].controls.sizeCode.value).toBeNull();
  });

  it('says why the dropdowns are empty when the sizes did not load', () => {
    setUp([DOMESTIC], UNUSED);
    service['listCylinderSizes'].mockReturnValue(throwError(() => new Error('offline')));
    const fixture = TestBed.createComponent(CylinderTypesPage);
    fixture.detectChanges();

    expect(fixture.componentInstance['noOptionsMessage']()).toBe(
      "The sizes didn't load. Use Retry above.",
    );
  });

  it('adds a cylinder by its size and saves its price in the same step', () => {
    const { page } = render();
    service['createCylinderType'].mockReturnValue(
      of({ ...DOMESTIC, id: 'new', name: '19 kg Commercial', category: 'commercial' }),
    );

    page['openCreateDrawer']();
    page['form'].controls.category.setValue('commercial');
    page['form'].patchValue({ sizeCode: 'commercial_19', price: 1750 });
    page['submit']();

    // The usual commercial rate is filled in.
    expect(service['createCylinderType']).toHaveBeenCalledWith('commercial_19', {
      hsnCode: '27111900',
      gstRatePercent: 18,
    });
    expect(priceService['setPrice']).toHaveBeenCalledWith('new', 'commercial', 1750);
    expect(notify.success).toHaveBeenCalled();
    expect(page['createDrawerVisible']()).toBe(false);
    expect(page['priceTarget']()).toBeNull();
  });

  it('fills the usual GST rate for the type, and keeps one the admin typed', () => {
    const { page } = render();
    const rate = page['form'].controls.gstRatePercent;

    page['openCreateDrawer']();
    page['form'].controls.category.setValue('domestic');
    expect(rate.value).toBe(5);
    page['form'].controls.category.setValue('commercial');
    expect(rate.value).toBe(18);

    rate.setValue(12);
    rate.markAsDirty();
    page['form'].controls.category.setValue('domestic');
    expect(rate.value).toBe(12);
  });

  it('opens the price drawer, filled in, when the new cylinder price fails to save', () => {
    const { page } = render();
    priceService['setPrice'].mockReturnValue(throwError(() => new Error('offline')));

    page['openCreateDrawer']();
    page['form'].controls.category.setValue('commercial');
    page['form'].patchValue({ sizeCode: 'commercial_19', price: 1750 });
    page['submit']();

    expect(page['createDrawerVisible']()).toBe(false);
    expect(page['priceTarget']()).toEqual(DOMESTIC);
    expect(page['suggestedPrice']()).toBe(1750);
    expect(notify.success).not.toHaveBeenCalled();
  });

  it('does not add without a price', () => {
    const { page } = render();

    page['openCreateDrawer']();
    page['form'].controls.category.setValue('commercial');
    page['form'].patchValue({ sizeCode: 'commercial_19' });
    page['submit']();

    expect(service['createCylinderType']).not.toHaveBeenCalled();
  });

  it('lists each cylinder with its price, or says it is not set', () => {
    const { page } = render([DOMESTIC, TYPED_BY_HAND]);

    expect(listed(page, 'c1').price_text).toContain('853');
    expect(listed(page, 'c2').price_text).toBe('Not set');
    expect(column(page, 'price_text')?.cellClass).toBeDefined();
    expect(columnFields(page)).not.toContain('hsn_code');
  });

  it('does not add without a size', () => {
    const { page } = render();

    page['openCreateDrawer']();
    page['form'].patchValue({ gstRatePercent: 18 });
    page['submit']();

    expect(service['createCylinderType']).not.toHaveBeenCalled();
  });

  it('keeps all its row buttons in one Actions column', () => {
    const done = render([DOMESTIC]).page;

    expect(columnFields(done)).not.toContain('gst_action');
    expect(columnFields(done).filter((field) => field === 'actions')).toHaveLength(1);
    expect(buttons(done, listed(done, 'c1'))).toEqual(['Change price', 'Deactivate']);
  });

  it('offers what each row still needs', () => {
    const { page } = render([DOMESTIC, TYPED_BY_HAND]);

    expect(buttons(page, listed(page, 'c2'))).toEqual(['Set price', 'Set GST', 'Deactivate']);
    expect(buttons(page, { ...listed(page, 'c1'), is_active: false })).toEqual(['Activate']);
  });

  it('shows the status as a chip, and exports it as the same word', () => {
    const status = column(render().page, 'is_active');

    expect(status?.cellRenderer).toBe(StatusChipCell);
    expect(status?.valueFormatter?.(false, {} as never)).toBe('Inactive');
  });

  it('opens the details from the name', () => {
    const { page } = render();

    page['columns'][0].onLinkClick?.(listed(page, 'c1'));

    expect(page['details']()).toEqual(DOMESTIC);
  });

  it('points out records that are not a standard size', () => {
    const { fixture } = render([DOMESTIC, TYPED_BY_HAND]);

    expect(fixture.nativeElement.textContent).toContain(
      'Not a standard cylinder size: 19KG_Domestic.',
    );
  });
});

describe('PriceDrawer', () => {
  const BRANCHES = [
    { id: 'b1', name: 'Kukatpally', is_active: true },
    { id: 'b2', name: 'Miyapur', is_active: true },
  ];

  function render(branches: typeof BRANCHES = [], suggested: number | null = null) {
    setUp([DOMESTIC], UNUSED);
    const fixture = TestBed.createComponent(PriceDrawer);
    fixture.componentRef.setInput('prices', [PRICE]);
    fixture.componentRef.setInput('branches', branches);
    fixture.componentRef.setInput('suggestedPrice', suggested);
    fixture.componentRef.setInput('cylinderType', DOMESTIC);
    fixture.detectChanges();
    return { fixture, drawer: fixture.componentInstance };
  }

  it('starts on the usual customer and shows the price now in force', () => {
    const { drawer } = render();

    expect(drawer['form'].getRawValue()).toEqual({
      customerType: 'domestic',
      branchId: null,
      price: null,
    });
    expect(drawer['title']()).toBe('Change price');
    expect(drawer['currentText']()).toContain('853');
  });

  it('says what the customer pays with GST', () => {
    const { drawer } = render();

    drawer['form'].patchValue({ price: 1000 });

    expect(drawer['hint']()).toContain('The customer pays');
    expect(drawer['hint']()).toContain('1,050');
  });

  it('asks for a branch only when there is more than one', () => {
    render([BRANCHES[0]]);
    expect(document.querySelector('#price-branch')).toBeNull();
    TestBed.resetTestingModule();
    document.body.innerHTML = '';

    render(BRANCHES);
    expect(document.querySelector('#price-branch')).not.toBeNull();
  });

  it('saves the price for all branches unless one is chosen', () => {
    const { drawer } = render(BRANCHES, 900);
    const saved = jest.fn();
    drawer.saved.subscribe(saved);

    drawer['save']();
    expect(priceService['setPrice']).toHaveBeenLastCalledWith('c1', 'domestic', 900, null);

    drawer['form'].patchValue({ branchId: 'b1' });
    expect(drawer['currentText']()).toContain('all-branches price');
    drawer['save']();
    expect(priceService['setPrice']).toHaveBeenLastCalledWith('c1', 'domestic', 900, 'b1');
    expect(saved).toHaveBeenCalledTimes(2);
  });

  it('does not save without a price above zero', () => {
    const { drawer } = render();

    drawer['save']();
    drawer['form'].patchValue({ price: 0 });
    drawer['save']();

    expect(priceService['setPrice']).not.toHaveBeenCalled();
  });
});

describe('CylinderTypeDrawer', () => {
  function render(
    type: CylinderTypeResponse,
    usage: CylinderTypeUsageResponse,
    others: CylinderTypeResponse[] = [],
  ) {
    setUp([type, ...others], usage);
    const fixture = TestBed.createComponent(CylinderTypeDrawer);
    fixture.componentRef.setInput('cylinderType', type);
    fixture.componentRef.setInput('allTypes', [type, ...others]);
    fixture.componentRef.setInput('sizes', SIZES);
    fixture.detectChanges();
    return { fixture, drawer: fixture.componentInstance };
  }

  it('points out a saved GST rate that is not the usual one', () => {
    const { fixture } = render({ ...DOMESTIC, gst_rate_percent: '18.00' }, UNUSED);

    expect(fixture.nativeElement.textContent).toContain(
      'GST on domestic LPG is usually 5%, not 18%.',
    );
  });

  it('warns while an unusual rate is typed, and not for the usual one', () => {
    const { fixture, drawer } = render(DOMESTIC, UNUSED);
    expect(fixture.nativeElement.textContent).not.toContain('Check with your accountant');

    drawer['startEdit'](DOMESTIC);
    drawer['form'].patchValue({ gstRatePercent: 18 });
    expect(drawer['editGstHint']()).toContain('usually 5%, not 18%');

    drawer['form'].patchValue({ gstRatePercent: 5 });
    expect(drawer['editGstHint']()).not.toContain('accountant');
  });

  it('shows the price and asks the page to change it', () => {
    const { fixture, drawer } = render(DOMESTIC, UNUSED);
    fixture.componentRef.setInput('prices', [PRICE]);
    fixture.detectChanges();
    const requested = jest.fn();
    drawer.priceRequested.subscribe(requested);

    expect(drawer['priceRows']()[0].label).toBe('Domestic · All branches');
    expect(drawer['priceRows']()[0].amount).toContain('853');
    const change = button(fixture.nativeElement, 'price');
    expect(change?.textContent).toContain('Change price');
    change?.click();

    expect(requested).toHaveBeenCalledWith(DOMESTIC);
  });

  it('keeps its actions in a footer below the scrolling details', () => {
    const { fixture } = render(DOMESTIC, UNUSED);
    const footer = (fixture.nativeElement as HTMLElement).ownerDocument.querySelector(
      '.detail-view > .modal-actions',
    );

    expect(footer?.querySelectorAll('button')).toHaveLength(3);
  });

  const button = (host: HTMLElement, action: string) =>
    host.querySelector<HTMLButtonElement>(`[data-action="${action}"]`);

  const offeredCodes = (drawer: CylinderTypeDrawer) =>
    drawer['editSizes']().map((size) => size.code);

  it('explains why a type in use cannot be deleted', () => {
    const { fixture } = render(DOMESTIC, USED);

    expect(button(fixture.nativeElement, 'delete')?.disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain(
      'It is used in stock records, so it cannot be deleted. Deactivate it instead.',
    );
  });

  it('still says why with a server that does not send what blocks a delete', () => {
    const older = { used_in: ['stock records'], allowed_size_codes: [] };

    const { fixture } = render(DOMESTIC, older as unknown as CylinderTypeUsageResponse);

    expect(button(fixture.nativeElement, 'delete')?.disabled).toBe(true);
    expect(button(fixture.nativeElement, 'edit')?.disabled).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('It is used in stock records');
  });

  it('lets a cylinder that only has a price be deleted', () => {
    const { fixture } = render(DOMESTIC, {
      used_in: ['prices'],
      delete_blocked_by: [],
      allowed_size_codes: ['domestic_14_2'],
    });

    expect(button(fixture.nativeElement, 'delete')?.disabled).toBe(false);
  });

  it('deletes an unused type only after confirming', () => {
    const { fixture, drawer } = render(DOMESTIC, UNUSED);
    const deleted = jest.fn();
    drawer.deleted.subscribe(deleted);

    button(fixture.nativeElement, 'delete')?.click();
    expect(service['deleteCylinderType']).not.toHaveBeenCalled();
    confirmations[0].accept?.();

    expect(service['deleteCylinderType']).toHaveBeenCalledWith('c1');
    expect(deleted).toHaveBeenCalled();
  });

  it('keeps Delete and Edit off, with a retry, when usage cannot be checked', () => {
    setUp([DOMESTIC], UNUSED);
    service['getUsage'].mockReturnValue(throwError(() => new Error('offline')));
    const fixture = TestBed.createComponent(CylinderTypeDrawer);
    fixture.componentRef.setInput('cylinderType', DOMESTIC);
    fixture.detectChanges();

    expect(button(fixture.nativeElement, 'delete')?.disabled).toBe(true);
    expect(button(fixture.nativeElement, 'edit')?.disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain("Couldn't check where this type is used.");
  });

  it('keeps the size of a type in use and saves only the GST change', () => {
    const { drawer } = render(DOMESTIC, USED);

    drawer['startEdit'](DOMESTIC);
    expect(offeredCodes(drawer)).toEqual(['domestic_14_2']);
    expect(drawer['sizeHint']()).toBe('This cylinder type is in use, so its size cannot change.');
    drawer['form'].patchValue({ gstRatePercent: 18 });
    drawer['save']();

    expect(service['updateCylinderType']).toHaveBeenCalledWith('c1', {
      sizeCode: undefined,
      gst: { hsnCode: '27111900', gstRatePercent: 18 },
    });
  });

  it('does not let a rate that is set be removed', () => {
    const { drawer } = render(DOMESTIC, USED);

    drawer['startEdit'](DOMESTIC);
    drawer['form'].patchValue({ gstRatePercent: null });
    drawer['save']();

    expect(service['updateCylinderType']).not.toHaveBeenCalled();
    expect(drawer['editing']()).toBe(true);
  });

  it('lets a hand-typed record take the standard size of its weight', () => {
    const { drawer } = render(TYPED_BY_HAND, {
      used_in: ['prices'],
      delete_blocked_by: [],
      allowed_size_codes: ['commercial_19'],
    });
    expect(drawer['offListAdvice']()).toContain('Choose Edit and pick its size.');

    drawer['startEdit'](TYPED_BY_HAND);
    drawer['form'].patchValue({ sizeCode: 'commercial_19' });
    drawer['save']();

    // No rate yet, so no GST is sent.
    expect(service['updateCylinderType']).toHaveBeenCalledWith('c2', {
      sizeCode: 'commercial_19',
      gst: undefined,
    });
  });

  it('says so when the matching standard size is already taken', () => {
    const taken = { ...DOMESTIC, id: 'c3', name: '19 kg Commercial' };

    const { drawer } = render(
      TYPED_BY_HAND,
      { used_in: ['prices'], delete_blocked_by: [], allowed_size_codes: ['commercial_19'] },
      [taken],
    );

    expect(offeredCodes(drawer)).toEqual([]);
    expect(drawer['offListAdvice']()).toContain('already in your list');
    expect(drawer['offListAdvice']()).toContain('deactivate this one');
  });

  it('does not ask to deactivate a record that is already inactive', () => {
    const taken = { ...DOMESTIC, id: 'c3', name: '19 kg Commercial' };

    const { drawer } = render(
      { ...TYPED_BY_HAND, is_active: false },
      { used_in: ['prices'], delete_blocked_by: [], allowed_size_codes: ['commercial_19'] },
      [taken],
    );

    expect(drawer['offListAdvice']()).toContain('so use that one.');
    expect(drawer['offListAdvice']()).not.toContain('deactivate');
  });

  it('shows the type and size of a record when editing starts', () => {
    const { drawer } = render(DOMESTIC, UNUSED);

    drawer['startEdit'](DOMESTIC);

    expect(drawer['form'].getRawValue()).toMatchObject({
      category: 'domestic',
      sizeCode: 'domestic_14_2',
    });
  });

  it('asks for a size when only the type was changed', () => {
    const { drawer } = render(DOMESTIC, UNUSED);

    drawer['startEdit'](DOMESTIC);
    drawer['form'].controls.category.setValue('commercial');
    drawer['save']();

    expect(service['updateCylinderType']).not.toHaveBeenCalled();
    expect(drawer['form'].controls.sizeCode.hasError('required')).toBe(true);
  });

  it('picks the type of a hand-typed record when only one is possible', () => {
    const { drawer } = render(TYPED_BY_HAND, {
      used_in: ['prices'],
      delete_blocked_by: [],
      allowed_size_codes: ['commercial_19'],
    });

    drawer['startEdit'](TYPED_BY_HAND);

    expect(drawer['form'].controls.category.value).toBe('commercial');
    expect(offeredCodes(drawer)).toEqual(['commercial_19']);
  });

  it('closes edit mode without a request when nothing changed', () => {
    const { drawer } = render(DOMESTIC, UNUSED);

    drawer['startEdit'](DOMESTIC);
    drawer['save']();

    expect(service['updateCylinderType']).not.toHaveBeenCalled();
    expect(drawer['editing']()).toBe(false);
  });
});
