import { TestBed } from '@angular/core/testing';
import { MarkdownPipe } from './markdown.pipe';

describe('MarkdownPipe', () => {
  let pipe: MarkdownPipe;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    pipe = TestBed.runInInjectionContext(() => new MarkdownPipe());
  });

  function render(value: string | null | undefined): string {
    const safe = pipe.transform(value);
    if (typeof safe === 'string') return safe;
    return (safe as { changingThisBreaksApplicationSecurity: string })
      .changingThisBreaksApplicationSecurity;
  }

  it('renders an empty string for null/undefined/empty input', () => {
    expect(render(null)).toBe('');
    expect(render(undefined)).toBe('');
    expect(render('')).toBe('');
  });

  it('renders headings, bold text and lists as real HTML', () => {
    const html = render('### Heading\n\n**bold** and a list:\n\n- one\n- two');
    expect(html).toContain('<h3>Heading</h3>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>one</li>');
  });

  it('renders a GitHub-flavored markdown table', () => {
    const html = render('| A | B |\n| --- | --- |\n| 1 | 2 |');
    expect(html).toContain('<table>');
    expect(html).toContain('<th>A</th>');
    expect(html).toContain('<td>1</td>');
  });

  it('strips a script tag and event-handler attribute injection attempt', () => {
    const html = render('<script>alert(1)</script>text with <img src=x onerror="alert(1)">');
    expect(html).not.toContain('<script');
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('<img');
    expect(html).toContain('text with');
  });

  it('forces target=_blank and rel=noopener noreferrer on links', () => {
    const html = render('[LPG](https://example.com)');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });
});
