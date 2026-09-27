# Buttons with a Brain

**Demo:** `/playground/motion`
**Component:** `web/src/components/practice/stateful-button.tsx`

## Behavior

The reusable button handles idle, loading, success, and error states. Native hover and focus styles cover pointer and keyboard use; the disabled prop uses the browser's native disabled behavior. During loading, activating the button cancels the request. A run ID prevents a late response from replacing the cancelled state. Success and error feedback stays visible for 1.6 seconds, then returns to idle; errors remain retryable.

The demo offers fixed “Always succeeds” and “Always fails” scenarios. Its 720 ms request simulation is local and needs no service. The live status region announces progress, cancellation, and results without relying on color or animation.

## Motion choices

The button lifts by 2 px on hover and active feedback settles immediately. State icons use a 150 ms opacity and scale transition; the button uses 200 ms. Both use the familiar ease-out curve so the response starts promptly and settles without a spring or bounce. These durations are long enough to register while staying out of the way of repeated actions. The spinner rotates while loading. `prefers-reduced-motion` removes transitions and rotation, while text and state colors keep the feedback understandable.

## Manual verification

- [ ] Tab to the demo controls and confirm the focus ring is visible; use Enter and Space to choose a scenario and start the action.
- [ ] Choose “Always succeeds”; run the request and confirm loading then success, followed by a return to idle.
- [ ] Choose “Always fails”; run the request and confirm loading then error, then retry successfully by changing the scenario.
- [ ] Activate the button during loading and confirm cancellation returns it to idle; confirm a late result cannot overwrite that state.
- [ ] Confirm the disabled example cannot be activated and is visually distinct.
- [ ] Enable `prefers-reduced-motion`; confirm text feedback remains and transitions/spinner rotation stop.
- [ ] Use a screen reader to confirm progress, cancellation, success, and error are announced by the status region.
