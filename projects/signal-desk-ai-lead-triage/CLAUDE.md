# Project guidance

## Stack and structure
- Next.js App Router, React, TypeScript, and Tailwind CSS.
- Keep routes as Server Components unless a feature needs browser state, event handlers, or browser APIs.
- Keep route handlers, model logic, and UI components in separate modules.
- Keep accessible practice widgets and the standalone React practice app under `playground/`.

## Conventions
- Use semantic HTML, visible focus, labelled controls, and keyboard support.
- Validate every API input at the server boundary with Zod; keep scoring pure and provider-independent.
- Keep API keys and model configuration server-side; never commit secrets.
- Prefer small pure functions for scoring, formatting, and validation.
- Use Conventional Commits and describe observable changes.
- Add tests for important user-visible states and keep tests independent of real AI services.
- Treat sample lead records and training examples as synthetic; never imply they are real customers.
- Put supporting evidence and model limitations next to scores, and test structured fields as well as free text.
