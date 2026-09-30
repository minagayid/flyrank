# Bioinformatics reviewer checklist

## Question and scope
- [ ] The question is limited to classifying human RefSeq transcript records as `NM_`/`NR_` operational coding status.
- [ ] FLIP2 results and variant information are not mixed into this study.

## Data and labels
- [ ] Confirm assembly `GCF_000001405.40` / GRCh38.p14.
- [ ] Confirm the downloaded annotation release, expected as `GCF_000001405.40-RS_2025_08`, from the package report.
- [ ] Confirm the NCBI Datasets CLI version and download timestamp are present in the manifest.
- [ ] Review NCBI Datasets/RefSeq data-use terms before redistribution.
- [ ] Review NM_ and NR_ counts, missingness, duplicates, and class balance.
- [ ] Review all `NR_` `gene_biotype` values, including lncRNA, miRNA, snRNA, tRNA, snoRNA, and rRNA where present.
- [ ] Inspect prefix-vs-GFF3 biotype mismatches; do not assume every mismatch is an error.

## QC and leakage control
- [ ] Confirm the minimum-length rule is only `>=20 nt` and is justified as a malformed/empty-sequence floor.
- [ ] Confirm short RNAs are retained rather than filtered out as a shortcut.
- [ ] Confirm isoforms are grouped by NCBI GeneID before clustering.
- [ ] Confirm MMseqs2 uses 80% nucleotide identity and 80% coverage for the primary split, and that every modeling record inherits a cluster.
- [ ] Confirm the assertions and printed tables show zero GeneID and cluster overlap between train, validation, and test.

## MMseqs2 threshold sensitivity
- [ ] Confirm the sweep covers 70%, 75%, 80%, 85%, 90%, and 95% nucleotide identity at fixed 80% coverage.
- [ ] Inspect the train/test leakage matrix at every audit threshold, not only the split's own threshold.
- [ ] Confirm own-threshold train/test overlap is zero for every split threshold.
- [ ] Compare generalization metrics across thresholds with the model-selection choice held fixed.
- [ ] Interpret threshold effects as sensitivity of the leakage/generalization trade-off, not as evidence that one identity threshold is universally correct.

## Modeling and interpretation
- [ ] Confirm preprocessing is fit on training data only and tuning uses validation only.
- [ ] Compare the majority baseline, interpretable length/GC/3-mer model, and TF-IDF model on the same split.
- [ ] Review test precision, recall, F1, AUROC, AUPRC, confusion matrix, and bootstrap intervals.
- [ ] Review validation-only seed sensitivity.
- [ ] Inspect errors by length, GC, biotype, and uncertain individual cases.
- [ ] Treat performance as evidence about this RefSeq sampling frame and operational labels, not as a validated biological coding predictor.
- [ ] Consider an external chromosome, assembly, or independent annotation holdout before making stronger claims.
