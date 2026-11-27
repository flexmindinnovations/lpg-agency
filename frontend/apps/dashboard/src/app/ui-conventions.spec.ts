import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

/**
 * The checkable half of "Dashboard UI conventions" in AGENTS.md. It reads the
 * source of every screen, so a new one that goes its own way fails here. When
 * a convention is added there, add its check here.
 */
const WORKSPACE = join(__dirname, '..', '..', '..', '..');

interface Source {
  readonly file: string;
  readonly text: string;
}

function sources(folder: string): Source[] {
  return readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
    const path = join(folder, entry.name);
    if (entry.isDirectory()) {
      return ['node_modules', 'dist', 'generated'].includes(entry.name) ? [] : sources(path);
    }
    if (!/\.(ts|html)$/.test(entry.name) || /\.(spec|stories)\.ts$/.test(entry.name)) return [];
    return [
      {
        file: relative(WORKSPACE, path).split(sep).join('/'),
        text: readFileSync(path, 'utf8'),
      },
    ];
  });
}

const SOURCES = [join(WORKSPACE, 'apps', 'dashboard', 'src'), join(WORKSPACE, 'libs')].flatMap(
  sources,
);

/** The opening tag of every `<name>` element; attribute values may hold `>`. */
function openingTags(text: string, name: string): string[] {
  const pattern = new RegExp(`<${name}(?=[\\s/>])(?:[^>"']|"[^"]*"|'[^']*')*>`, 'g');
  return text.match(pattern) ?? [];
}

/** `file: what is wrong`, so a failure says where to look. */
function offenders(find: (source: Source) => string[]): string[] {
  return SOURCES.flatMap((source) => find(source).map((what) => `${source.file}: ${what}`));
}

const matches = (pattern: RegExp) => (source: Source) => source.text.match(pattern) ?? [];

/** Grid column objects written out in a file (nested up to two deep). */
const columnObjects = (source: Source) =>
  source.text.match(/\{\s*field: '[^']+',(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}/g) ?? [];

/** The `{ icon, text, …, onAction }` objects given to `rowActionsColumn`. */
const rowActionObjects = (source: Source) =>
  (
    source.text.match(/\{(?:\s|\/\/[^\n]*\n)*icon: (?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}/g) ?? []
  ).filter((object) => object.includes('onAction:'));

const oneLine = (code: string) => code.replace(/\s+/g, ' ').slice(0, 90);

const outsideSharedUi = (found: string) => !found.startsWith('libs/shared/ui/');

describe('Dashboard UI conventions (AGENTS.md)', () => {
  it('reads the screens it is meant to check', () => {
    const selects = SOURCES.flatMap((source) => openingTags(source.text, 'p-select'));

    expect(SOURCES.length).toBeGreaterThan(100);
    expect(selects.length).toBeGreaterThan(100);
  });

  it('gives every dropdown a search box that clears when it closes', () => {
    const unsearchable = offenders((source) =>
      openingTags(source.text, 'p-select')
        .filter(
          (tag) => !/\s\[filter\]="true"/.test(tag) || !/\s\[resetFilterOnHide\]="true"/.test(tag),
        )
        .map(oneLine),
    );

    expect(unsearchable).toEqual([]);
  });

  it('uses one kind of dropdown', () => {
    expect(offenders(matches(/<(p-autocomplete|p-dropdown|select)(?=[\s/>])/g))).toEqual([]);
  });

  it('uses the shared status chip, not a page of its own', () => {
    const own = offenders(matches(/class \w+Status\w*Cell\b/g)).filter(outsideSharedUi);

    expect(own).toEqual([]);
  });

  it('builds the Actions column with rowActionsColumn', () => {
    // A data column may be headed "Action" (what was done) if it is a chip.
    const handBuilt = offenders((source) =>
      columnObjects(source)
        .filter((column) => /header: 'Actions?'/.test(column) && !column.includes('ActionChipCell'))
        .map(oneLine),
    ).filter(outsideSharedUi);

    expect(handBuilt).toEqual([]);
  });

  it('makes a row button red when it deletes, removes or switches off', () => {
    const plain = offenders((source) =>
      rowActionObjects(source)
        .filter((action) => /text: [^\n]*'(Delete|Remove|Deactivate)\b/.test(action))
        .filter((action) => !/severity:[^\n]*'danger'/.test(action))
        .map(oneLine),
    );

    expect(SOURCES.flatMap(rowActionObjects).length).toBeGreaterThan(5);
    expect(plain).toEqual([]);
  });

  it('heads each section with a section card, not a bare heading', () => {
    const bare = offenders(
      matches(/<h[2-6][^>]*class="(?:section-title|section-heading|detail-heading)"[^>]*>/g),
    );

    expect(bare).toEqual([]);
  });

  it("draws a table's border once, so a card can turn its sides off", () => {
    // AG Grid frames the table again inside our own border, and that inner
    // frame ignores the section card.
    const grid = SOURCES.find((source) => source.file.endsWith('/data-grid.component.ts'));

    expect(grid?.text).toContain('--ag-wrapper-border: none;');
  });

  it('shows a record with the label on the left and its value beside it', () => {
    // A totals strip above a table is a set of figures, not a record.
    const TOTALS_STRIPS = ['cash-handover-register.html', 'daily-sales.html', 'gst-filing.html'];
    const ownLayout = offenders((source) =>
      TOTALS_STRIPS.some((name) => source.file.endsWith(`/${name}`))
        ? []
        : openingTags(source.text, 'dt')
            .filter((tag) => !/class="(detail-label|info-label|detail-field__label)\b/.test(tag))
            .map(oneLine),
    );

    expect(ownLayout).toEqual([]);
  });

  it('gives every side drawer one of the two shared widths', () => {
    // The customer profile is a full record beside its list; the notification
    // panel is sized by its own stylesheet.
    const OWN_SIZE = /max\(45vw|lpg-notification-drawer/;
    const ownWidth = offenders((source) =>
      openingTags(source.text, 'p-drawer')
        .filter((tag) => !tag.includes('var(--drawer-width') && !OWN_SIZE.test(tag))
        .map(oneLine),
    ).filter(outsideSharedUi);

    expect(ownWidth).toEqual([]);
  });

  it('does not use link text as a row button', () => {
    // A link opens the record named in its cell; anything else is a button.
    const linkButtons = offenders((source) =>
      columnObjects(source)
        .filter(
          (column) => column.includes('onLinkClick') && /field: '(id|action|actions)'/.test(column),
        )
        .map(oneLine),
    );

    expect(linkButtons).toEqual([]);
  });

  it('shows a state in a grid as a chip', () => {
    // Column objects whose field names a state, without a chip renderer.
    const STATE_FIELD =
      /field: '(status|is_active|is_enabled\w*|kyc_status|payment_status|app_login|role|booking_source)'/;
    const plain = offenders((source) =>
      columnObjects(source)
        .filter((column) => STATE_FIELD.test(column) && !column.includes('cellRenderer:'))
        .map(oneLine),
    );

    expect(plain).toEqual([]);
  });
});
