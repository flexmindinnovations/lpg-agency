# 20 — Animation Guidelines

## Purpose
Designs micro-interactions, loading, transitions, table updates, and notifications, all token-driven and fully respecting prefers-reduced-motion.

## 1. Motion Principles
Motion communicates state change, never decorates (`01-product-principles.md`). Every animation answers "what changed and where did it go or come from" — if an animation cannot be justified that way, it does not ship.

## 2. Micro-Interactions
- Button hover/active: background-color transition, 100ms (micro duration token).
- Checkbox/radio toggle: 100ms scale plus color transition on the indicator.
- Input focus: border-color and focus-ring transition, 100ms.
- These are the platform's most frequent animations by far (every click/hover) and are kept intentionally fast and subtle — never springy/bouncy, which would feel unprofessional in this enterprise context.

## 3. Loading States
- Skeleton screens (not spinners) for initial content load on List and Detail screens (`07-wireframe-specifications.md` Templates A/B) — a subtle shimmer animation (1.5s loop) indicates active loading without implying false progress.
- Spinners reserved for indeterminate, short-duration operations (button submit, inline action) where a full skeleton would be overkill.
- Progress bars used only where genuine determinate progress is available (large report export, file upload) — never a fake progress bar.

## 4. Transitions (Navigation and Overlays)
- Drawer open/close: slide plus fade, 250ms (medium duration token), decelerate easing on open, standard easing on close.
- Dialog open/close: scale (98 percent to 100 percent) plus fade, 250ms.
- Route/page transitions: no full-page transition animation on the Dashboard (instant navigation, consistent with the Linear/GitHub benchmark's snappy feel) — only the content area's skeleton-to-loaded transition provides perceived motion.
- Tab switching (within a Detail screen): content cross-fade, 150ms (small duration token).

## 5. Table Updates (Data Grid)
- Row insertion/removal (after a filter change or real-time update): 150ms fade plus height animation, so the user's eye tracks what changed rather than experiencing an instant jarring layout shift.
- Cell value updates (e.g. a live-updating Order status in the Live Delivery Tracking grid): brief background-color flash (highlight pulse, 400ms, fading to transparent) on the specific changed cell — draws attention to exactly what updated without disrupting the rest of the grid.

## 6. Notifications (Toast/Snackbar)
- Toast enters via slide plus fade from the notification stack's anchor position (bottom-right on Dashboard, top on mobile apps per platform convention), 150ms.
- Auto-dismisses after 5 seconds for informational toasts; persists until manually dismissed for error toasts requiring acknowledgment.
- Multiple simultaneous toasts stack vertically with a slight offset, never overlapping.

## 7. Motion Tokens (Reference)
Full token values in `09-design-tokens.md` section 7 — duration scale (micro/small/medium/large) and easing curves (standard/decelerate), plus the parallel reduced-motion duration scale.

## 8. Reduced Motion Handling
Every animation category above (sections 2 through 6) has its duration substituted from the reduced-motion token set when prefers-reduced-motion is active — durations drop to near-zero (0-50ms) and any transform-based motion (slide, scale) is replaced with an opacity-only transition, never fully removing the state-change feedback. The one deliberate, documented exception is the Button loading spinner (`13-component-specifications.md` Worked Spec 1), which continues rotating under reduced motion since a stopped loading indicator would misrepresent actual state.

## Best Practices
- No animation exceeds 350ms (large duration token) — anything longer starts to feel sluggish in a daily-use operational tool.
- Animations are implemented via CSS transitions/transforms (GPU-accelerated properties: opacity, transform) wherever possible, never animating layout-triggering properties except where explicitly needed (e.g. accordion expand), for performance.

## Risks
- Overuse of the cell-flash highlight pattern on a rapidly-updating Live Delivery Tracking grid could become visually noisy — mitigated by rate-limiting the highlight to genuinely meaningful status changes, not every minor field update.

## Alternatives Considered
- Spring-physics-based animation (bouncy, playful motion) — rejected; inconsistent with the calm, professional visual language benchmarked against Linear/Stripe/Atlassian.

## Future Scalability
- The token-driven duration/easing scale means a future platform-wide motion-personality adjustment is a token-value change, not a per-component animation rewrite.
