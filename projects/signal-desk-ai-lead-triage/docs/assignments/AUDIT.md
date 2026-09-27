# Accessibility and performance audit

## Scope

Review the inbox, lead workspace, accessible widget lab, motion states, and both visual playgrounds. Check keyboard-only operation, visible focus, labels and names, error announcements, text contrast, 320 px reflow, reduced-motion behavior, and low-end mobile rendering. Use Lighthouse accessibility/performance and WAVE on the exact built version being reviewed.

## Current record

| Check | Status | Evidence |
|---|---|---|
| Semantic structure and keyboard paths | Component tests pass; manual keyboard and screen-reader review pending | Component tests and FE-03 notes |
| Automated WCAG A/AA scan | Passed with 0 reported violations on six primary routes in Chromium and Firefox | Playwright + axe-core; local runs on 2026-09-25 |
| Keyboard dialog path | Passed focus entry, wrap, Escape, and focus return in Chromium and Firefox | Playwright browser check on 2026-09-25 |
| Reduced motion and responsive reflow | Passed emulated reduced-motion and 320 px overflow checks in Chromium and Firefox | Playwright browser check on inbox, lead, and practice routes; WebGL fallback remains code-reviewed only |
| Lighthouse mobile profile | Inbox 96 performance / 100 accessibility; lead review 97 / 98 | [Inbox JSON](../audits/lighthouse-inbox-2026-09-25.json), [lead JSON](../audits/lighthouse-lead-2026-09-25.json); local production build, 2026-09-25. Original HTML reports remain in ignored `outputs/`. |
| Placeholder text contrast | Improved from 3.14:1 to 5.27:1 on white (`#849590` → `#606f6b`); the new color measures 4.74:1 on the app's `#eff4f1` paper | WCAG relative-luminance contrast calculation; `web/src/app/globals.css` |
| WAVE violations | Not measured | WAVE extension report still required; no WAVE zero-error claim |
| Baseline versus after comparison | Not measured | Requires a stable preview URL |
| Mobile and browser matrix | Lighthouse mobile profile plus 320 px checks; Chromium and Firefox | Other browsers and physical devices remain unchecked |

## Repeatable audit

1. Start the production build locally and open each route at 320 px, 768 px, and desktop width.
2. Lighthouse mobile reports are saved for the inbox and lead workspace. Repeat on a stable public preview before comparing revisions.
3. Run WAVE on the same URLs and record every error or contrast alert. Fix issues and rerun before claiming the capstone threshold.
4. Use keyboard only to traverse the nav, filter, open/close the dialog, change tabs, reveal disclosure content, submit a question, stop a response, and reach the static controls on reduced motion.
5. Compare performance with the visual playgrounds unloaded versus opened. Record actual values and device conditions; do not infer a score from implementation choices.

Both pages exceed the capstone's Lighthouse performance threshold of 85. The six-route axe scan reports no violations in two browser engines. A contrast review found the chat placeholder below the 4.5:1 text target; its color was darkened and now measures 5.27:1 on white and 4.74:1 on the app paper. WAVE, manual screen-reader review, a stable-URL baseline comparison, and physical-device checks remain open; automated scans do not replace those checks.
