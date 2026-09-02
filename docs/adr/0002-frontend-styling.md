# ADR 0002 — hand-written CSS tokens instead of Tailwind

status: accepted · date: 2026-09-02 · amends: D7

## Context

D7 said "Vue 3 + Vite + TS + Pinia + ECharts, styled with Tailwind and the
tokens defined in the design document". The approved UI was delivered as
hand-written CSS in `docs/design/architecture.html` and every mockup there is
already expressed as plain classes over CSS custom properties.

## Decision

Keep the token system, drop Tailwind. `frontend/src/styles/tokens.css` holds the
palette and type tokens verbatim from the approved design; `app.css` holds the
component classes the mockups use.

## Consequences

* The shipped UI is a direct transcription of the approved mockups instead of a
  re-derivation in utility classes.
* One less build dependency and no PostCSS pipeline to keep in step.
* Trade-off: no utility classes, so new components must add their own rules.
  Acceptable at this size; if the component count grows past what one stylesheet
  can hold, revisit and introduce Tailwind then.
