# 24 — Flutter Design Guidelines

## Purpose
Designs the Flutter UI architecture for the Customer and Driver mobile apps: Material 3, Riverpod, responsive layout, offline UX, adaptive components.

## 1. Material 3
Both apps use Material 3 (Material You) as the base widget/interaction layer, with the platform's design tokens (`09-design-tokens.md` section 12) applied via a custom theme extension rather than Material's default color scheme — Material 3 provides accessible, well-tested interaction affordances (ripple effects, elevation semantics, adaptive component behavior); the visual language on top is fully the platform's own token-driven system, not stock Material styling, consistent with the Angular side's approach to Angular Material (`23-angular-design-guidelines.md` section 6).

## 2. Riverpod
- Riverpod (code-generation flavor) is the state management layer across both apps, matching the approved Mobile Architecture.
- Providers are organized by feature (order list provider, delivery confirmation provider), never a single monolithic app-state provider.
- The Application-layer/Domain-layer split from the approved Mobile Architecture is reflected in UI code: widgets consume Notifiers (Application layer), never reaching directly into repository/data-layer code.

## 3. Responsive Layout
- Both apps are built mobile-first (phone portrait as the base layout), with adaptive breakpoint widgets handling the tablet secondary layout (`19-responsive-design.md` section 6) — e.g. Order History converts from a single-column list to a two-pane list-plus-detail layout above a defined tablet width threshold.
- No fixed pixel layouts — all spacing/sizing uses the token-driven spacing constants (`09-design-tokens.md` section 12), scaled appropriately for Flutter's logical-pixel model.

## 4. Offline UX
- Driver App (primary offline-first target, D-24): every screen that displays or captures data is designed to function identically whether online or offline — the UI never blocks on a network round-trip for a core delivery action (`07-wireframe-specifications.md` Worked Example 2). The Sync Status screen (DR-10) is the single, consistent place a driver checks connectivity/queue state; individual screens show only a subtle, non-blocking sync indicator, never a full-screen offline interruption.
- Customer App (online-first, offline-tolerant): cached read data (recent orders, cylinder balance) displays with a last-updated timestamp when offline; write actions (booking, complaints) show a clear, friendly message if attempted offline rather than silently queuing, since booking isn't a D-24 offline-mandatory flow the way delivery confirmation is.

## 5. Adaptive Components
- Components adapt their touch-target size and information density based on which app they're used in even when visually similar (e.g. a shared Card widget renders with the Driver App's larger touch targets and higher-contrast styling by default in that app's theme context, versus the Customer App's slightly warmer, standard-density styling) — achieved via the theme extension's per-app token values, not per-widget conditional logic.
- Platform-adaptive behavior (iOS vs Android conventions) uses Flutter's adaptive widget patterns where they improve familiarity, without breaking the shared visual design system's consistency.

## Best Practices
- Every screen widget is tested with Flutter widget tests covering its Loading/Empty/Error/Success states (`07-wireframe-specifications.md` templates), matching the Angular side's Storybook-driven state coverage discipline.
- Accessibility: every interactive widget provides a semantics label; the Driver App in particular is tested with TalkBack/VoiceOver given the persona's lower average tech comfort (`02-user-personas.md`).

## Risks
- Divergence between the Flutter theme extension values and the canonical token JSON (`09-design-tokens.md` section 1) is the primary cross-platform consistency risk — mitigated by generating the Dart theme constants from the same source JSON as the Angular/CSS output, never hand-maintained independently.

## Alternatives Considered
- BLoC instead of Riverpod — both valid; Riverpod chosen per the approved Mobile Architecture for lower boilerplate and stronger compile-time safety in code-generation mode.
- A fully custom (non-Material) widget system — rejected; Material 3's accessible interaction scaffolding is a strong foundation not worth rebuilding from scratch, matching the Angular Material decision on the Dashboard side.

## Future Scalability
- The adaptive-per-app-theme-context approach means a future third mobile app (unlikely but structurally supported) could reuse the entire shared widget package with just a new theme extension instance, no widget-level changes.
