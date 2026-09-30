# CRISPR-Cas9 sequence ML extension

This extension adapts the new transcript notebook's ideas to a **public SITE-seq off-target/activity benchmark**:

- sequence-derived, position-aware mismatch features;
- an extended PAM-proximal mismatch feature with fold-local start/weight selection;
- guide-grouped cross-validation so the same intended guide is not in train and test;
- a transparent mismatch/seed baseline beside a learned model;
- continuous ranking against the SITE-seq 4 nM cleavage signal;
- saved provenance, source SHA-256, bootstrap intervals, and limitations.

## Run

From the repository root:

```bash
python3 crispr/run_offtarget_study.py
```

The script downloads the public workbook at runtime into `work/crispr_cache/` (ignored by Git) and writes:

- `outputs/crispr/study_results.json`
- `outputs/crispr/study_report.md`
- `outputs/crispr/site_seq_ranked_review.csv`

The refined activity ranker reaches **Spearman ρ = 0.2132**, compared with **0.2090** for the original mismatch/seed baseline. The extended window starts at position 11 in three outer folds and position 10 in one fold, with weights of 4.0 or 5.0. These choices are selected inside inner grouped folds; they are not tuned on the held-out rows.

No benchmark dataset is committed.

## What the model does—and does not do

The activity task predicts an assay-specific 4 nM SITE-seq cleavage signal from mismatch positions and GC features. The ON/OFF classifier is retained as a sanity screen, but its near-perfect score is expected because exact intended-guide matches are trivially different from off-target rows; it is not the headline scientific result.

The random-forest comparison is also retained in the result manifest. It does not beat the refined ranker on this small grouped benchmark, which is why the published artifact favors the simpler, interpretable feature rule.

The ranking is **not** a genome-wide off-target search, a clinical recommendation, or an experimental substitute. Before any biological use, rerun against the chosen reference assembly and cell context with a validated aligner/off-target tool, then use independent experimental review and validation.

## Public evidence

- SITE-seq workbook and curated data index: [dagrate/public_data_crisprCas9](https://github.com/dagrate/public_data_crisprCas9)
- Foundational guide-design study: [Doench et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4744125/)
- Guide-design benchmark: [Bradford et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6738662/)
- Broad GPP scoring documentation: [Azimuth and CFD overview](https://portals.broadinstitute.org/gpp/public/software/sgrna-scoring-help)
