# Portfolio Evidence Editor evaluation scorecard

Published: 14 August 2026

Suite: 12 synthetic, public-safe labeled-note cases

Evaluator: [`evaluate.py`](evaluate.py)

Test set: [`test-set.json`](test-set.json)

The comparison column is a deliberately narrow formatter-only baseline. It parses
the same labels but does not detect missing sections, risky language, numeric tokens,
or empty input. It is a reproducible reference point, not a claim about a hidden
historical implementation.

| Metric | Formatter-only baseline | Current v2 rules |
|---|---:|---:|
| Complete labeled input | 5/5 | 5/5 |
| Missing-section detection | 0/3 | 3/3 |
| Risky-language detection | 0/3 | 3/3 |
| Numeric-token audit | 0/5 | 5/5 |
| Empty-input refusal | 0/1 | 1/1 |

Run it from this directory with:

```bash
python evaluate.py
```

The scorecard measures whether the deterministic guardrails fire on labeled
fixtures. It does not measure semantic truth, privacy compliance, writing quality,
or whether a project outcome generalizes beyond these cases.
