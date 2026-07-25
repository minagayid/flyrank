# Week 9 — Break Your Own Site

Portfolio: https://minagayid.github.io/flyrank/

Reviewer: Codex structured hardening review, 25 July 2026.

## Where it breaks

### Fixed now

- **Empty calculator submission:** native required fields plus explicit numeric checks prevent an undefined result.
- **Clicks greater than impressions:** the tool now explains the contradiction instead of returning a negative or misleading score.
- **Zero impressions:** click-through rate resolves safely to zero; no division error is shown.
- **Negative values:** rejected by both input constraints and JavaScript validation.
- **Very narrow screens:** project cards, the calculator, footer, and actions collapse into one readable column.
- **Keyboard use:** the skip link, semantic form labels, and real buttons support keyboard navigation.
- **Screen-reader result:** calculator feedback is written to a polite live region.
- **Broken public root:** the starter README was replaced with a focused portfolio.
- **Findability:** page title, meta description, canonical URL, Open Graph title/description/image, theme color, and favicon were added.
- **Heavy assets:** the root uses no raster images, framework bundle, webfont, or build pipeline.

### Known limitations

- The GitHub Pages fallback URL includes the project path `/flyrank/`; a paid personal domain can replace it later.
- The official FlyRank graduate badge cannot be installed until the portal accepts a capstone and issues the credential.
- Open Graph preview behavior depends on each social platform refreshing its cache.
- Anonymous pageview analytics uses a public, rate-limited counter and does not provide private audience segmentation.
- The Portfolio Evidence Editor is a transparent rule-based workflow, not a semantic fact-checker.
- A final physical-phone check must be performed by the owner; this review used a phone-sized browser viewport.

## Click and edge-case review

- Root navigation anchors resolve to Work, Live tool, and About.
- GitHub, paper, notebook, agent, and evidence links use explicit public URLs.
- Repeated calculator submissions replace the prior result cleanly.
- Rapid double-submit does not create network calls or duplicate records because the feature is local-only.
- The analytics request is non-blocking; failure degrades to a text status and never breaks the page.

## Hardening verdict

The must-fix list is addressed. Remaining limitations are named in the interface or evidence notes and do not create a false security, performance, credential, or causal claim.
