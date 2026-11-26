import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ConfirmationService, type Confirmation } from 'primeng/api';
import { of, throwError } from 'rxjs';
import {
  AdminCylinderTypeService,
  NotifyService,
  type CylinderTypeResponse,
  type CylinderTypeUsageResponse,
} from '@lpg/shared/data-access';
import { CylinderTypeDrawer } from './cylinder-type-drawer';
import { CylinderTypesPage } from './cylinder-types-page';

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
  allowed_size_codes: SIZES.map((size) => size.code),
};
const USED: CylinderTypeUsageResponse = {
  used_in: ['stock records', 'prices'],
  allowed_size_codes: ['domestic_14_2'],
};

let service: Record<string, jest.Mock>;
let confirmations: Confirmation[];

function setUp(types: CylinderTypeResponse[], usage: CylinderTypeUsageResponse): void {
  confirmations = [];
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
      { provide: NotifyService, useValue: { success: jest.fn(), error: jest.fn() } },
      {
        provide: ConfirmationService,
        useValue: { confirm: (c: Confirmation) => confirmations.push(c) },
      },
    ],
  });
}

describe('CylinderTypesPage', () => {
  function render(types: CylinderTypeResponse[] = [DOMESTIC]) {
    setUp(types, UNUSED);
    const fixture = TestBed.createComponent(CylinderTypesPage);
    fixture.detectChanges();
    return { fixture, page: fixture.componentInstance };
  }

  const columnFields = (page: CylinderTypesPage) => page['columns']().map((column) => column.field);

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

  it('adds a type by its size, not by a typed name or weight', () => {
    const { page } = render();

    page['openCreateDrawer']();
    page['form'].controls.category.setValue('commercial');
    page['form'].patchValue({ sizeCode: 'commercial_19', gstRatePercent: 18 });
    page['submit']();

    expect(service['createCylinderType']).toHaveBeenCalledWith('commercial_19', {
      hsnCode: '27111900',
      gstRatePercent: 18,
    });
  });

  it('does not add without a size', () => {
    const { page } = render();

    page['openCreateDrawer']();
    page['form'].patchValue({ gstRatePercent: 18 });
    page['submit']();

    expect(service['createCylinderType']).not.toHaveBeenCalled();
  });

  it('drops "Set GST" once every type has a rate', () => {
    const { page } = render([DOMESTIC]);

    expect(columnFields(page)).not.toContain('gst_action');
  });

  it('offers "Set GST" only on the rows without a rate', () => {
    const { page } = render([DOMESTIC, TYPED_BY_HAND]);
    const column = page['columns']().find((c) => c.field === 'gst_action');

    expect(column?.valueFormatter?.(undefined, DOMESTIC)).toBe('');
    expect(column?.valueFormatter?.(undefined, TYPED_BY_HAND)).toBe('Set GST');
  });

  it('opens the details from the name', () => {
    const { page } = render();

    page['columns']()[0].onLinkClick?.(DOMESTIC);

    expect(page['details']()).toEqual(DOMESTIC);
  });

  it('points out records that are not a standard size', () => {
    const { fixture } = render([DOMESTIC, TYPED_BY_HAND]);

    expect(fixture.nativeElement.textContent).toContain(
      'Not a standard cylinder size: 19KG_Domestic.',
    );
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

  const button = (host: HTMLElement, action: string) =>
    host.querySelector<HTMLButtonElement>(`[data-action="${action}"]`);

  const offeredCodes = (drawer: CylinderTypeDrawer) =>
    drawer['editSizes']().map((size) => size.code);

  it('explains why a type in use cannot be deleted', () => {
    const { fixture } = render(DOMESTIC, USED);

    expect(button(fixture.nativeElement, 'delete')?.disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain(
      'It is used in stock records and prices, so it cannot be deleted. Deactivate it instead.',
    );
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
      { used_in: ['prices'], allowed_size_codes: ['commercial_19'] },
      [taken],
    );

    expect(offeredCodes(drawer)).toEqual([]);
    expect(drawer['offListAdvice']()).toContain('already in your list');
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
