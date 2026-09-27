# AI-assisted workflow drill

## Branch exercise

The comparison lives in `workflow/vague-prompt` (`5c89d0d`) and `workflow/precise-prompt` (`605fb5f`). The vague prompt asks for a lead inbox that “looks better and more modern.” It can open a design space, but it leaves the assistant to guess which details matter, what should happen on a phone, and how an empty result should read.

The precise prompt asks for a compact review workspace for a small creative studio. Show the lead, fit signal, budget, timeline, and next action. Keep score evidence visible, filter by score band, explain zero results, work at 320 px, and make clear that a score cannot decide whether to accept or price a project. These criteria make the task reviewable without dictating every visual detail.

The vague branch preserves the first draft’s fixed 78%, 58%, and 42% signal bars. During review, those numbers looked like model measurements despite having no measured source. The precise branch replaces them with counts calculated from feature matches across the four synthetic examples and labels the sample size. The comparison shows why a polished screen can still make an unsupported claim.

## Corrections found in review

The first budget feature matched a bare four-digit amount. It missed `$8,000`, so the classifier recognized that a budget existed without recognizing its fit band. Comparing the feature extraction pattern with the sample data exposed the mismatch. The pattern now covers comma-separated amounts in both structured fields and free text, with tests for each form. The data remains synthetic; this fix does not calibrate the score against real outcomes.

Review also caught that an interrupted assistant response was removed even though the edge-case brief promised to preserve partial text. The UI now keeps any received words, restores the question, and exposes retry. A component test covers that recovery path, and an API test confirms that the simulated stream emits text before its error state.

## Three project rules

1. Keep routes as Server Components unless a page needs browser state, event handlers, or a browser API.
2. Validate requests with Zod at the server boundary, and keep scoring in pure functions that run without an external provider.
3. Label every example as synthetic; show score evidence and limits beside a recommendation, and leave the decision with a person.

The detailed implementation, data source, and model limitations are in `SPEC.md`, `docs/AI_WORKLOG.md`, and `docs/capstone/REFLECTION.md`. Both workflow branches and the comparison are public in the repository; the FE-04 portal submission is saved and awaits mentor review.
