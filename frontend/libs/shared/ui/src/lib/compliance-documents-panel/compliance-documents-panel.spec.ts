import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import {
  ComplianceDocumentsPanel,
  type ComplianceDocumentItem,
} from './compliance-documents-panel';

const PENDING: ComplianceDocumentItem = {
  id: 'd1',
  doc_type: 'rc',
  document_number: 'MH12AB1234',
  issue_date: '2022-08-03',
  expiry_date: '2999-08-02',
  verification_status: 'pending',
  rejection_reason: null,
  file_url: 'https://example.test/rc.pdf',
};

const REJECTED: ComplianceDocumentItem = {
  ...PENDING,
  id: 'd2',
  issue_date: null,
  expiry_date: '2000-01-01',
  verification_status: 'rejected',
  rejection_reason: 'Scan is cut off',
};

describe('ComplianceDocumentsPanel', () => {
  function render(
    documents: ComplianceDocumentItem[],
    {
      permissions = ['vehicles:manage', 'compliance:verify'],
      reviewEnabled = true,
    }: { permissions?: string[]; reviewEnabled?: boolean } = {},
  ) {
    TestBed.configureTestingModule({
      providers: [
        { provide: PERMISSION_CHECKER, useValue: () => ({ permissions: new Set(permissions) }) },
      ],
    });
    const verify = jest.fn(() => of({}));
    const fixture = TestBed.createComponent(ComplianceDocumentsPanel);
    const set = (name: string, value: unknown) => fixture.componentRef.setInput(name, value);
    set('documents', documents);
    set('docTypeOptions', [{ label: 'Registration certificate (RC)', value: 'rc' }]);
    set('managePermission', 'vehicles:manage');
    set('reviewEnabled', reviewEnabled);
    set('uploader', () => of({ blobRef: 'ref' }));
    set('addDocument', () => of({}));
    set('replaceDocument', () => of({}));
    set('verifyDocument', verify);
    fixture.detectChanges();

    const cards = () => [...fixture.nativeElement.querySelectorAll('.cdp__card')] as HTMLElement[];
    const text = (element: Element) => element.textContent?.replace(/\s+/g, ' ').trim() ?? '';
    const facts = (card: HTMLElement) =>
      [...card.querySelectorAll('.cdp__fact')].map((fact) => [
        text(fact.querySelector('dt') as Element),
        text(fact.querySelector('dd') as Element),
      ]);
    const actions = (card: HTMLElement) =>
      [...card.querySelectorAll('.cdp__actions a, .cdp__actions button')].map(text);
    const press = (card: HTMLElement, label: string) => {
      const button = [...card.querySelectorAll('button')].find((b) => text(b) === label);
      expect(button).toBeDefined();
      button?.click();
      fixture.detectChanges();
    };
    return { fixture, cards, text, facts, actions, press, verify };
  }

  it('shows each document as a card with labelled details', () => {
    const { cards, text, facts } = render([PENDING, REJECTED]);

    expect(cards()).toHaveLength(2);
    expect(text(cards()[0])).toContain('Registration certificate (RC)');
    expect(facts(cards()[0])).toEqual([
      ['Number', 'MH12AB1234'],
      ['Issue date', expect.stringContaining('2022')],
      ['Expiry date', expect.stringContaining('2999')],
    ]);
    // No issue date on file: no empty row. An old expiry date is flagged.
    expect(facts(cards()[1]).map(([label]) => label)).toEqual(['Number', 'Expiry date']);
    expect(facts(cards()[1])[1][1]).toContain('Expired');
    expect(text(cards()[1])).toContain('Rejected: Scan is cut off');
  });

  it('offers review only on a pending document', () => {
    const { cards, actions } = render([PENDING, REJECTED]);

    expect(actions(cards()[0])).toEqual(['View file', 'Replace', 'Reject', 'Verify']);
    expect(actions(cards()[1])).toEqual(['View file', 'Replace']);
  });

  it('hides what the user may not do', () => {
    const { cards, actions } = render([PENDING], { permissions: [] });

    expect(actions(cards()[0])).toEqual(['View file']);
  });

  it('keeps only the file link when review is switched off', () => {
    const { cards, actions } = render([PENDING], { reviewEnabled: false });

    expect(actions(cards()[0])).toEqual(['View file']);
  });

  it('verifies a document', () => {
    const { cards, press, verify } = render([PENDING]);

    press(cards()[0], 'Verify');

    expect(verify).toHaveBeenCalledWith('d1', { status: 'verified' });
  });

  it('asks for a reason in the card before rejecting', () => {
    const { cards, actions, press, verify } = render([PENDING]);

    press(cards()[0], 'Reject');

    // The card's own Reject and Verify give way to the form.
    expect(actions(cards()[0])).toEqual(['View file', 'Replace']);
    press(cards()[0], 'Confirm reject');
    expect(verify).not.toHaveBeenCalled();
    expect(cards()[0].textContent).toContain('A reason is required');

    press(cards()[0], 'Cancel');
    expect(actions(cards()[0])).toEqual(['View file', 'Replace', 'Reject', 'Verify']);
  });
});
