import { DomSanitizer, type SafeHtml } from '@angular/platform-browser';
import { Pipe, type PipeTransform, inject } from '@angular/core';
import DOMPurify from 'dompurify';
import { marked } from 'marked';

/**
 * Safe subset of tags/attributes a rendered answer may use — enough for
 * real prose (headings, emphasis, lists, tables, code, quotes, links) with
 * nothing that could execute script or style-inject, since this renders
 * LLM-generated text (`AI Command Center`, ADR-045) that could in principle
 * echo adversarial content back from a tool result.
 */
const ALLOWED_TAGS = [
  'p',
  'br',
  'hr',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'strong',
  'em',
  'del',
  'ul',
  'ol',
  'li',
  'a',
  'blockquote',
  'code',
  'pre',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
];
const ALLOWED_ATTR = ['href', 'target', 'rel'];

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

/**
 * Renders a markdown string (e.g. an AI Command Center answer) as sanitized
 * HTML for `[innerHTML]` binding. `marked` parses GitHub-flavored markdown
 * (tables included); `DOMPurify` strips anything outside the safe prose
 * subset above before Angular ever sees the HTML — defense-in-depth beyond
 * Angular's own `[innerHTML]` sanitizer, since this is model-generated
 * text, not content the app itself authored.
 */
@Pipe({ name: 'lpgMarkdown', standalone: true, pure: true })
export class MarkdownPipe implements PipeTransform {
  private readonly sanitizer = inject(DomSanitizer);

  transform(value: string | null | undefined): SafeHtml {
    if (!value) return '';
    const rawHtml = marked.parse(value, { gfm: true, breaks: true, async: false });
    const cleanHtml = DOMPurify.sanitize(rawHtml, { ALLOWED_TAGS, ALLOWED_ATTR });
    return this.sanitizer.bypassSecurityTrustHtml(cleanHtml);
  }
}
