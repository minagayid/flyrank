# Error, empty, and edge states

The controls below exercise failure paths locally. All leads and training examples are synthetic. The demo has no external model dependency, so a provider outage is not part of the shipped flow.

| Scenario | How to reach it | Expected recovery |
|---|---|---|
| No matching lead filter | Choose a score band with no matching sample | The inbox shows an explicit empty result and a reset path. |
| Invalid lead ID | Visit `/leads/not-a-sample` | Next.js returns its not-found page; no guessed record is shown. |
| Missing question or short description | Send an invalid JSON payload to `/api/qualify` | The route returns a 400 without opening a stream. |
| Malformed JSON | Send an invalid JSON body to `/api/qualify` | The route returns a readable 400 error. |
| Oversized request | Send more than 6 KB to `/api/qualify` | The route returns 413 before scoring. |
| Short-term rate limit | Send more than 20 requests from one forwarded address per minute | The route returns 429 and a `Retry-After` header. The in-memory limit is per process and is not a substitute for a shared production limiter. |
| Tool execution failure | On a lead page in development, choose **Tool error** | The four-state panel becomes an error, the user question remains, and retry is available. |
| Stream interruption | On a lead page in development, choose **Stop mid-stream** | Partial text remains visible with a retry action. |
| User stops a response | Start an analysis and choose **Stop** | The fetch is aborted; another question can be submitted. |
| Health endpoint unavailable | Visit `/health` when `/api/health` cannot be reached | The fetched-data page explains the failure instead of showing stale data. |
| WebGL unavailable | Open the 3D or shader playground in a browser without WebGL | A CSS illustration remains visible and useful. |
| Reduced motion | Enable the OS reduced-motion setting and open motion/visual playgrounds | Transitions are minimized and animated scenes remain still. |

The `demoFailure` switches are rejected in production. Validation and size checks happen before scoring. Assistant drafts are read-only suggestions and are never sent automatically.

## Evidence status

The UI exposes deterministic local tool-error and mid-stream interruption controls. The stream-interruption recovery is covered by an API test and a workspace component test; the complete test record is in `TESTING.md`. The other matrix entries are documented recovery expectations and have not all been exercised in a browser.
