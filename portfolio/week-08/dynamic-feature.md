# Week 8 — Make It Do Something

Live feature: https://minagayid.github.io/flyrank/#lab

## What shipped

One dynamic feature: a browser-based content opportunity scorer derived from the capstone baseline.

The visitor enters three public-safe aggregate values—impressions, clicks, and average search position. The tool validates the values, computes click-through rate, applies the baseline gate, and returns either a review recommendation or a monitor recommendation. The result explicitly asks for query-intent and SERP review before any content change.

## End-to-end data flow

1. The visitor types aggregate values into three HTML inputs.
2. JavaScript in the page reads those values after the visitor presses **Score this page**.
3. The browser checks that values are numeric, non-negative, and internally consistent.
4. If the page has at least 100 impressions and an average position from 5 to 20, the browser calculates `impressions × (1 − clicks / impressions)`.
5. The browser writes the result into an accessible live region.
6. Nothing is uploaded or stored.

## What a backend is

A backend is code that runs on a server rather than inside the visitor's browser. It commonly receives requests, applies business logic, talks to a database or another service, and returns a response.

This feature intentionally does **not** need a backend. Its calculation is small, deterministic, and safe to expose. Keeping it in the browser makes the privacy boundary visible: no entered data leaves the device.

## Real tests

| Case | Input | Expected result | Observed |
|---|---|---|---|
| Eligible review candidate | 1,200 impressions, 36 clicks, position 11.4 | Score 1,164.0 and review guidance | Pass |
| Too little evidence | 50 impressions, 1 click, position 9 | Monitor, do not prioritize | Pass |
| Outside position gate | 1,200 impressions, 36 clicks, position 2.5 | Monitor, do not prioritize | Pass |
| Contradictory input | 10 impressions, 20 clicks, position 8 | Explain that clicks cannot exceed impressions | Pass |
| Empty/invalid input | Missing or negative value | Accessible validation guidance | Pass |

The feature uses no paid service, API key, database, or private input.
