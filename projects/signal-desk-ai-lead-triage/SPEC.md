# Product brief

**Signal Desk** helps independent creative studios review project inquiries, decide which conversation to handle next, and ask useful follow-up questions. Its intended users are studio owners and small client-facing teams who receive incomplete requests through email or web forms. The product uses an explainable local text classifier to surface evidence about fit and urgency; a person makes every decision and edits any follow-up before sending. The first release focuses on a lead inbox, a qualification workspace, transparent score evidence, saved notes, and graceful recovery when analysis fails.

## Scope and AI role

- Show a curated set of clearly synthetic sample leads and a responsive lead list/detail view.
- Score lead fit from the request text with a small, documented logistic-regression model trained on synthetic examples.
- Stream a concise, evidence-linked explanation and render the score as a typed result component.
- Let the user ask follow-up questions in a constrained chat; never send a message or reject a lead automatically.
- Keep analysis available without a provider key. The local model is the default and the project documents its synthetic training data and limitations.

## Screens

1. `/` — lead inbox and attention summary.
2. `/leads/[id]` — lead context, model evidence, conversation, notes, and editable follow-up draft.
3. `/playground/accessibility` — hand-built dialog, tabs, and disclosure plus shadcn/ui comparison notes.
4. `/playground/react-practice` — standalone React practice application and AI work log.
5. `/playground/motion` — five-state button demonstration with success and failure controls.
6. `/playground/3d` — lazy 3D signal study with a static fallback.
7. `/playground/shader` — personalized shader hero and reduced-motion fallback.
8. `/health` — fetched health payload and route status.

## Out of scope

- Real customer data, user accounts, automated lead rejection, and automated outbound messages.
- A paid provider, hidden API credentials, or claims of a deployed/public version before one is verified.
- Claims of human research, user sessions, production traffic, Lighthouse results, or CI runs that were not observed.
