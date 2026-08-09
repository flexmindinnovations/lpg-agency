#!/usr/bin/env node
/**
 * Design token generator.
 *
 * Reads the single platform-neutral source (`design-tokens/tokens.json`) and
 * emits, for each target platform, exactly the same values:
 *
 *   frontend/libs/shared/design-tokens/src/lib/tokens.css   CSS custom properties
 *   frontend/libs/shared/design-tokens/src/lib/tokens.ts    typed TS constants
 *   mobile/packages/design_system/lib/src/tokens.dart       Dart constants
 *
 * `docs/ui/09-design-tokens.md` requires exactly this: one JSON source
 * generating every platform's output, "never hand-authored per platform".
 * Two hand-maintained token sets drift within weeks, and the drift shows up as
 * a Flutter screen that is subtly the wrong blue.
 *
 * Usage:
 *   node scripts/generate-tokens.mjs
 *   node scripts/generate-tokens.mjs --check   # verify, exit 1 on drift
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = resolve(ROOT, 'design-tokens/tokens.json');

const OUTPUTS = {
  css: resolve(ROOT, 'frontend/libs/shared/design-tokens/src/lib/tokens.css'),
  ts: resolve(ROOT, 'frontend/libs/shared/design-tokens/src/lib/tokens.ts'),
  dart: resolve(ROOT, 'mobile/packages/design_system/lib/src/tokens.dart'),
};

const THEMES = ['light', 'dark', 'highContrast'];
const THEME_ATTR = { light: 'light', dark: 'dark', highContrast: 'high-contrast' };

const BANNER = [
  'GENERATED FILE — DO NOT EDIT BY HAND.',
  'Source: design-tokens/tokens.json',
  'Regenerate: node scripts/generate-tokens.mjs',
].join('\n');

// ---------------------------------------------------------------------------
// Source reading and reference resolution
// ---------------------------------------------------------------------------

const tokens = JSON.parse(readFileSync(SOURCE, 'utf8'));

/** Resolve a `{primitive.color.blue.600}` reference against the source tree. */
function resolveRef(value) {
  let current = value;
  let guard = 0;
  while (typeof current === 'string' && current.startsWith('{') && current.endsWith('}')) {
    if (++guard > 10) throw new Error(`Circular token reference: ${value}`);
    const path = current.slice(1, -1).split('.');
    let node = tokens;
    for (const segment of path) {
      node = node?.[segment];
      if (node === undefined) throw new Error(`Unresolved token reference: ${current}`);
    }
    current = node;
  }
  return current;
}

const isMeta = (key) => key.startsWith('$');
const kebab = (s) => s.replace(/([a-z0-9])([A-Z])/g, '$1-$2').replace(/_/g, '-').toLowerCase();

/** True when a node is a per-theme value object rather than a nested group. */
const isThemed = (node) =>
  node && typeof node === 'object' && THEMES.some((theme) => theme in node);

/**
 * Walk the source and collect flat token entries.
 * Themed values produce one entry per theme; everything else is theme-neutral.
 */
function collect(node, path = [], out = []) {
  for (const [key, value] of Object.entries(node)) {
    if (isMeta(key)) continue;
    const next = [...path, key];

    if (isThemed(value)) {
      out.push({
        name: next.map(kebab).join('-'),
        pathParts: next,
        themed: true,
        values: Object.fromEntries(THEMES.map((t) => [t, resolveRef(value[t])])),
      });
    } else if (value && typeof value === 'object') {
      collect(value, next, out);
    } else {
      // `value` here is a leaf — usually a string reference like
      // `{semantic.color.action.primary}`. `resolveRef` follows the chain
      // until it lands on something that isn't itself a `{...}` reference,
      // but that landing spot can be a *themed* object (e.g. component.button
      // .primaryBackground references semantic.color.action.primary, which is
      // themed) rather than a plain primitive. Only the isThemed(value) branch
      // above ever produced a themed entry, so a reference-to-a-themed-value
      // fell through to here and got stringified as the value itself —
      // "[object Object]" in CSS, silently dropped in Dart. Re-checking the
      // *resolved* result (not just the raw, pre-resolution value) for
      // theming is what closes that gap.
      const resolved = resolveRef(value);
      if (isThemed(resolved)) {
        out.push({
          name: next.map(kebab).join('-'),
          pathParts: next,
          themed: true,
          values: Object.fromEntries(THEMES.map((t) => [t, resolveRef(resolved[t])])),
        });
      } else {
        out.push({
          name: next.map(kebab).join('-'),
          pathParts: next,
          themed: false,
          value: resolved,
        });
      }
    }
  }
  return out;
}

const GROUPS = ['semantic', 'typography', 'elevation', 'motion', 'opacity', 'zIndex', 'component'];
const entries = GROUPS.flatMap((group) =>
  tokens[group] ? collect(tokens[group], [group === 'semantic' ? '' : group].filter(Boolean)) : [],
);

// Primitives are emitted too, so a token can be inspected in devtools, but
// application code must reference semantic or component tokens only.
const primitives = collect(tokens.primitive, ['primitive']);

// ---------------------------------------------------------------------------
// CSS
// ---------------------------------------------------------------------------

function buildCss() {
  const lines = [`/*\n${BANNER}\n*/\n`];

  const neutral = [...primitives, ...entries.filter((e) => !e.themed)];
  lines.push(':root {');
  for (const entry of neutral) lines.push(`  --${entry.name}: ${entry.value};`);
  lines.push('');
  lines.push('  /* Light is the default theme; no attribute required. */');
  for (const entry of entries.filter((e) => e.themed)) {
    lines.push(`  --${entry.name}: ${entry.values.light};`);
  }
  lines.push('}\n');

  for (const theme of ['dark', 'highContrast']) {
    lines.push(`[data-theme='${THEME_ATTR[theme]}'] {`);
    for (const entry of entries.filter((e) => e.themed)) {
      lines.push(`  --${entry.name}: ${entry.values[theme]};`);
    }
    lines.push('}\n');
  }

  // System preference, only when the user has not chosen explicitly.
  lines.push("@media (prefers-color-scheme: dark) {");
  lines.push("  :root:not([data-theme]) {");
  for (const entry of entries.filter((e) => e.themed)) {
    lines.push(`    --${entry.name}: ${entry.values.dark};`);
  }
  lines.push('  }');
  lines.push('}\n');

  // Reduced motion is a WCAG 2.2 AA requirement, not a nicety.
  lines.push('@media (prefers-reduced-motion: reduce) {');
  lines.push('  :root {');
  for (const [key, value] of Object.entries(tokens.motion.reducedMotion.duration)) {
    if (isMeta(key)) continue;
    lines.push(`    --motion-duration-${kebab(key)}: ${value};`);
  }
  lines.push('  }');
  lines.push('}');

  return lines.join('\n') + '\n';
}

// ---------------------------------------------------------------------------
// TypeScript
// ---------------------------------------------------------------------------

function buildTs() {
  const lines = [`/**\n * ${BANNER.split('\n').join('\n * ')}\n */\n`];

  lines.push('export const THEMES = [');
  for (const theme of THEMES) lines.push(`  '${THEME_ATTR[theme]}',`);
  lines.push('] as const;\n');
  lines.push('export type Theme = (typeof THEMES)[number];\n');

  lines.push('/** CSS custom property names, for programmatic access. */');
  lines.push('export const tokenVars = {');
  for (const entry of [...primitives, ...entries]) {
    const key = entry.pathParts.map((p, i) => (i === 0 ? p : p[0].toUpperCase() + p.slice(1))).join('');
    lines.push(`  ${JSON.stringify(key)}: '--${entry.name}',`);
  }
  lines.push('} as const;\n');
  lines.push('export type TokenName = keyof typeof tokenVars;\n');

  lines.push('/**');
  lines.push(' * Read a token value at runtime.');
  lines.push(' *');
  lines.push(' * Only for cases where a token is needed in logic rather than CSS —');
  lines.push(' * computing a chart series colour, for example. Styling always goes');
  lines.push(' * through the CSS custom property directly.');
  lines.push(' */');
  lines.push('export function readToken(name: TokenName, element: HTMLElement = document.documentElement): string {');
  lines.push('  return getComputedStyle(element).getPropertyValue(tokenVars[name]).trim();');
  lines.push('}');

  return lines.join('\n') + '\n';
}

// ---------------------------------------------------------------------------
// Dart
// ---------------------------------------------------------------------------

const dartName = (parts) =>
  parts
    .map((p, i) => (i === 0 ? p : p[0].toUpperCase() + p.slice(1)))
    .join('')
    .replace(/[^A-Za-z0-9]/g, '');

function toDartValue(value) {
  if (typeof value !== 'string') return `'${value}'`;
  const hex = value.match(/^#([0-9a-fA-F]{6})$/);
  if (hex) return `Color(0xFF${hex[1].toUpperCase()})`;
  const px = value.match(/^(-?[\d.]+)px$/);
  if (px) return `${px[1]}`;
  const ms = value.match(/^(\d+)ms$/);
  if (ms) return `Duration(milliseconds: ${ms[1]})`;
  if (/^-?[\d.]+$/.test(value)) return value;
  return `'${value}'`;
}

function buildDart() {
  const lines = [`// ${BANNER.split('\n').join('\n// ')}\n`];
  lines.push("import 'package:flutter/material.dart';\n");
  lines.push('/// Design tokens, generated from the same source as the web tokens.');
  lines.push('///');
  lines.push('/// Wired into a ThemeExtension by `LpgTheme` so widgets consume');
  lines.push('/// theme-scoped values rather than referencing these directly.');
  lines.push('abstract final class LpgTokens {');

  for (const entry of primitives) {
    lines.push(`  static const ${dartName(entry.pathParts)} = ${toDartValue(entry.value)};`);
  }
  lines.push('');

  for (const entry of entries.filter((e) => !e.themed)) {
    const value = toDartValue(entry.value);
    if (value.startsWith("'") && !/^'[\d.]+'$/.test(value)) continue; // skip CSS-only values
    lines.push(`  static const ${dartName(entry.pathParts)} = ${value};`);
  }
  lines.push('}\n');

  for (const theme of THEMES) {
    lines.push(`/// ${THEME_ATTR[theme]} theme colour values.`);
    lines.push(`abstract final class LpgTokens${theme[0].toUpperCase()}${theme.slice(1)} {`);
    for (const entry of entries.filter((e) => e.themed)) {
      const value = toDartValue(entry.values[theme]);
      if (!value.startsWith('Color(') && !/^[\d.]+$/.test(value)) continue;
      lines.push(`  static const ${dartName(entry.pathParts)} = ${value};`);
    }
    lines.push('}\n');
  }

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Write / check
// ---------------------------------------------------------------------------

const generated = { css: buildCss(), ts: buildTs(), dart: buildDart() };
const check = process.argv.includes('--check');
let drifted = false;

for (const [target, path] of Object.entries(OUTPUTS)) {
  const content = generated[target];
  if (check) {
    const current = existsSync(path) ? readFileSync(path, 'utf8') : null;
    if (current !== content) {
      console.error(`DRIFT: ${path}`);
      drifted = true;
    }
  } else {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, content, 'utf8');
    console.log(`Wrote ${path}`);
  }
}

if (check) {
  if (drifted) {
    console.error('\nGenerated token files are out of date. Run: node scripts/generate-tokens.mjs');
    process.exit(1);
  }
  console.log('OK: generated token files match design-tokens/tokens.json');
}
