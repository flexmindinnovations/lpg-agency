# QA fixes — dashboard-wide UI/UX (engineer: ui)

Branch `qa-fix/ui`. Scope: shared components (`libs/shared/*`), the app shell,
and surgical edits in feature templates.

## Shared date format (DA-31, DO-08) — for other engineers

Use `@lpg/shared/util` everywhere a date is shown or typed:

- `formatDisplayDate(v)` → "20 Oct 2026"; `formatDisplayDateTime(v)` → "20 Oct 2026, 10:09" (24-hour, IST).
  Date-only API strings ("2026-10-20") are never shifted by a time-zone conversion.
- Pipes `LpgDatePipe` (`| lpgDate`) and `LpgDateTimePipe` (`| lpgDateTime`) for templates.
- `toIsoDate(date)` → "2026-10-20" for API `date` fields (no UTC shift of a picked day).
- `parseDisplayDate('15/06/1985')`, `DATE_INPUT_FORMAT` ('dd/mm/yy'), `DATE_INPUT_PLACEHOLDER` ('dd/mm/yyyy').
- Every `p-datepicker` now reads dd/mm/yyyy by default (PrimeNG `translation.dateFormat` in
  `app.config.ts`) — do not set `dateFormat` on a datepicker.
- `@lpg/shared/ui`'s `formatReportDate` / `formatTimestamp` now delegate to these.

## Findings
