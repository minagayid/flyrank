# CRISPR-Cas9 sequence ML extension

This extension adapts the new transcript notebook's ideas to a **public SITE-seq off-target/activity benchmark**:

- sequence-derived, position-aware mismatch features;
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

No benchmark dataset is committed.

## What the model does—and does not do

The activity task predicts an assay-specific 4 nM SITE-seq cleavage signal from mismatch positions and GC features. The ON/OFF classifier is retained as a sanity screen, but its near-perfect score is expected because exact intended-guide matches are trivially different from off-target rows; it is not the headline scientific result.

The ranking is **not** a genome-wide off-target search, a clinical recommendation, or an experimental substitute. Before any biological use, rerun against the chosen reference assembly and cell context with a validated aligner/off-target tool, then use independent experimental review and validation.

## Public evidence

- SITE-seq workbook and curated data index: [dagrate/public_data_crisprCas9](https://github.com/dagrate/public_data_crisprCas9)
- Foundational guide-design study: [Doench et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4744125/)
- Guide-design benchmark: [Bradford et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6738662/)
- Broad GPP scoring documentation: [Azimuth and CFD overview](https://portals.broadinstitute.org/gpp/public/software/sgrna-scoring-help)
