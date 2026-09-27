# React app practice

Route: `/playground/react-practice`

This is a standalone React exercise built from the portal brief. It has a searchable list of synthetic studio inquiries, a selected row state, clear pressed-state semantics, and a useful empty result. It uses `useState` for user input and selection, and `useMemo` for a derived filtered list. The filtering never mutates the example source records.

## Assignment-derived implementation brief

The coding assistant received this focused implementation brief derived from the assignment: Build one App Router React page for practice, not a second product dashboard. Use three synthetic lead cards. Let a user search by studio name or service, select and deselect a card, and announce the selection. Use a controlled input, semantic buttons and labels, preserve the list when the query is empty, and show a short no-results message. Keep it responsive and avoid external APIs.

## Code review and corrections

The code review checked controlled input state, stable keys, case-insensitive matching, selection toggling, and the no-results path. The component stays local to the practice route so it does not create a second data source for the main application. The dollar amounts and names are invented examples. The page does not send a lead or contact anyone.

The referenced React video was not available in the provided materials during this session, so I did not claim to have watched it. This exercise focuses on the brief's React state and component requirements.

## Learning notes

- Store only the user's query and selection; derive the filtered list from the source array.
- Use a button with `aria-pressed` when a row toggles between selected and unselected.
- Give the empty result a clear message rather than rendering a blank list.
