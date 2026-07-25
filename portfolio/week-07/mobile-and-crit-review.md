# Week 7 — Mobile Audit and Structured Crit

Live portfolio: https://minagayid.github.io/flyrank/

## Proof statement

I turn ambiguous AI and machine-learning problems into useful, inspectable tools: public-safe inputs, reproducible evidence, honest limitations, and a clear human decision at the end.

## Mobile and accessibility fix log

### Before

- The root URL rendered the starter-repository README, so a visitor could not tell what Mina did within ten seconds.
- The primary evidence was buried among setup instructions intended for interns.
- The page did not present a focused contact or next action.
- The deployed capstone and agent work were not discoverable from a concise project surface.
- The old root was readable but not a real portfolio; mobile visitors had to scroll through a very long technical README.

### After

- Replaced the starter landing page with a dedicated, responsive portfolio.
- Added a one-sentence proof statement at the top and two direct actions.
- Added concise project cards with live and source links.
- Added a 46-pixel minimum target size for primary actions and form controls.
- Added a skip link, semantic headings, visible focus behavior, live-region feedback, responsive type, and a one-column mobile layout below 760 pixels.
- Added explicit input validation so invalid or contradictory values produce readable guidance.
- Added title, description, canonical URL, Open Graph metadata, theme color, and favicon.
- Kept the page image-light and dependency-free so text and controls remain crisp at every width.

## Link and responsive checks

- Portfolio root: reachable over HTTPS.
- Capstone paper: linked from the first work card.
- Capstone notebook: linked to the public repository.
- Portfolio Evidence Editor: linked from the second work card.
- GitHub profile: linked from the hero.
- Mobile layout: checked at 390 × 844 CSS pixels; content stacks in reading order with no horizontal overflow.
- Tablet/desktop layout: two-column project and tool layouts collapse cleanly on narrow screens.

The browser audit uses a phone-sized viewport. A final physical-device tap check remains the owner's last launch step because this environment cannot operate a separate handset.

## Structured review

Reviewer: Codex, acting as an external structured reviewer on 25 July 2026.

### Ten-second answers

1. **What does Mina do?** He builds evidence-first applied-AI and machine-learning tools that convert ambiguous questions into inspectable recommendations.
2. **Would I believe he is good at it?** The capstone paper and working browser tools provide credible proof. The main gap was not quality of work but the absence of a focused landing page.

### Must-fix

- Replace the starter README at the public root with a real personal portfolio.
- Put the proof statement above the fold.
- Make the capstone and working agent reachable in one click.
- Explain the decision boundary: the scorer prioritizes human review and does not claim causal ranking effects.
- Provide mobile-safe controls and honest validation states.

All five must-fixes are addressed on the live build.

### Nice-to-have

- Replace the pending FlyRank credential marker with the official badge after capstone acceptance.
- Add a real portrait or project capture only when it improves proof rather than decoration.
- Move from the clean GitHub Pages fallback URL to a paid personal domain when budget allows.
- Add another case study after the first external project ships.

## Review response

I accepted the central criticism: the previous public root proved repository activity but did not prove what I do. The new version leads with the role, shows two pieces of evidence, includes one live calculator, and names limitations instead of defending the old README-based page.
