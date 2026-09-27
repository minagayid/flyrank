# Visual plan — Signal Desk

## Direction

Design an intake room for a small studio: crisp, calm, and evidence-led. The interface should feel like a lead card has been pulled from a studio's physical inbox. One distinctive motif is a narrow perforated rule that separates a lead's original words from the model's evidence; the rest stays quiet and functional.

## Tokens

| Name | Hex | Role |
|---|---|---|
| Deep Tide | `#20363D` | Navigation and primary text |
| Mineral Paper | `#EFF4F1` | Main canvas |
| Sea Glass | `#3E7771` | Positive actions and confirmed fit |
| Brass | `#A86F2C` | Attention, timing, and cautious emphasis |
| Chalk Line | `#D2DEDA` | Dividers and quiet controls |
| Berry Ink | `#7D526A` | AI annotation and secondary signal |

Typography uses **DM Sans** for interface copy and **IBM Plex Mono** for score evidence and compact data. Headings are left-aligned; paragraphs stay below 72 characters per line. Avoid oversized hero metrics, gradient washes, repeated identical cards, and all-caps metadata.

## Layout sketch

```text
┌───────────┬──────────────────────────────────────────────┐
│ navigation│ Lead review     04 need attention            │
│           ├───────────────────────┬──────────────────────┤
│ inbox     │ intake slips          │ evidence / next step │
│ follow-up │ company + request     │ score + explanation │
│ settings  │ status + activity     │ chat + editable draft│
└───────────┴───────────────────────┴──────────────────────┘
```

On phones the navigation collapses, the selected lead becomes a full-width route, and the evidence rail follows the source request. No critical action depends on hover.

## Review before build

The cool paper palette and perforated intake slip tie the interface to the studio's lead-review job. The design's memorable element is the evidence rail; 3D and shader exercises live behind optional playground routes so they do not compete with the working tool or its initial-load performance.
