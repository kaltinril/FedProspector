# Phase 311: ESLint 9 → 10 Upgrade

**Status:** DEFERRED — blocked on eslint-plugin-jsx-a11y ecosystem catch-up
**Priority:** LOW (no security advisories on ESLint 9.x)
**Dependencies:** None — can land any time once the blocker clears
**Extracted from:** Phase 310 (PR 7) on 2026-04-18

---

## Context

This phase was originally PR 7 inside [Phase 310 — Dependency Updates](310-DEPENDENCY-UPDATES.md). It was extracted into its own phase on 2026-04-18 so that Phase 310 can close cleanly once PR 9 (TypeScript 6) lands, rather than remain open indefinitely waiting on an external ecosystem catch-up that has no timeline.

ESLint 9.x has zero open security advisories, so there is no pressure to ship this. It is a clean, low-risk upgrade that only needs to wait for one peer-dep range to widen.

---

## Blocker

`eslint-plugin-jsx-a11y@6.10.2` (latest on npm) declares peer `eslint ^3 || ... || ^9` — it does not accept ESLint 10. It is the de-facto JSX accessibility linter with no real replacement; removing it would drop a11y linting coverage.

`typescript-eslint@8.58.2` and `eslint-plugin-react-hooks@7.1.1` already support ESLint 10 — jsx-a11y is the sole holdout.

Tracking issue: **jsx-a11y #1075** (filed 2026-02-09, no progress as of 2026-04-18).

### No security pressure

ESLint 9.x has zero open advisories. Only old ReDoS `< 4.18.2` is flagged on `npm audit`, and we are far past that.

---

## Resume Conditions

Reopen this phase when either of the following happens:

(a) `eslint-plugin-jsx-a11y` ships a release with `eslint ^10` in its peer range, OR
(b) A viable replacement emerges.

### Watch list

- jsx-a11y releases (https://github.com/jsx-eslint/eslint-plugin-jsx-a11y/releases) and issue #1075
- `typescript-eslint`'s peer range (currently 8.58.2 supports both TS 5.x and TS 6) — confirm it still accepts ESLint 10 at time of resume
- Any replacement JSX a11y linter that gains real adoption

---

## Target Versions

| Package | Current | Target |
|---------|---------|--------|
| eslint | 9.39.4 | **10.x latest** |
| @eslint/js | 9.39.4 | **10.x latest** |
| eslint-plugin-react-hooks | 7.1.1 | verify still on a version supporting ESLint 10 |
| typescript-eslint | 8.58.2 | verify peer range still allows ESLint 10 (keep on a version that supports TS 5.x so this PR does not force TS 6) |
| eslint-plugin-jsx-a11y | 6.10.2 | **whatever version adds `eslint ^10` peer** |

---

## Upgrade Plan

1. Bump `eslint` 9.39.4 → 10.x latest
2. Bump `@eslint/js` 9.39.4 → 10.x latest
3. Bump `eslint-plugin-jsx-a11y` to the release that accepts `eslint ^10`
4. Keep `typescript-eslint` on a version that still supports TS 5.x (so this PR does not force TS 6 yet)
5. `npm run lint` — fix violations from 3 new `recommended` rules:
   - `no-unassigned-vars`
   - `no-useless-assignment`
   - `preserve-caught-error` (may affect `catch (e)` blocks that don't re-throw)
6. `npm run build`

---

## Code Impact Analysis (validated 2026-04-18)

- **Flat config already in use** — `ui/eslint.config.js` is the only config file; no `.eslintrc*` legacy config
- **Peer-dep compatibility verified** — `typescript-eslint@8.58.2` officially supports TS 6 ✓; `eslint-plugin-react-hooks@7.1.1` supports ESLint 10 ✓; `eslint-plugin-jsx-a11y@6.10.2` is the holdout ✗
- **Expect new violations from 3 new `recommended` rules**:
  - `no-unassigned-vars`
  - `no-useless-assignment`
  - `preserve-caught-error` (may affect `catch (e)` blocks that don't re-throw)
- **Process:** bump → `npm run lint` → fix violations file-by-file → commit

---

## Verification

- `cd ui && npm run lint` — passes
- `cd ui && npm run build` — passes
- `cd ui && tsc -b` — passes
- `cd ui && npm audit` — remains 0 vulnerabilities
- Tech stack doc in [../reference/11-TECH-STACK.md](../reference/11-TECH-STACK.md) updated with new ESLint version

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| New `recommended` rules surface many violations | Fix file-by-file in the same PR; all three rules are well-understood |
| typescript-eslint peer range silently drops ESLint 10 by the time we resume | Re-verify peer ranges at resume time before bumping |
| jsx-a11y release also bumps its own major and breaks rule names | Read release notes when it lands; migrate rule IDs if needed |
