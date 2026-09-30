# Human RefSeq transcript coding-status study

## Question
Can simple nucleotide sequence features distinguish human RefSeq transcripts labeled by accession prefix as protein-coding (`NM_`) versus non-coding (`NR_`)? FLIP2 results and variant information are out of scope.

## Data source and labels
- **Source:** NCBI Datasets human GRCh38.p14, accession `GCF_000001405.40`, downloaded with `--include rna,gff3`.
- **Requested annotation release:** `GCF_000001405.40-RS_2025_08`; the notebook records the runtime package/CLI metadata and should be checked against the downloaded report.
- **Operational label:** `NM_` → protein-coding (1); `NR_` → non-coding (0). `XM_`/`XR_` predicted models are excluded.
- **Audit:** reports NM_/NR_ counts, all `NR_` GFF3 `gene_biotype` values, prefix/GFF mismatches, class balance, missingness, duplicates, and length distributions.
- **License/provenance:** NCBI Datasets/RefSeq public data-use terms apply. Review the NCBI source page and package README before redistribution; this project does not relicense the source data.

## Split and minimum length
The modeling pool applies only `length >= 20 nt` as a malformed/empty-sequence QC floor. This is intentionally not a biological cutoff, because short `NR_` RNAs (miRNA, tRNA, snRNA, etc.) are retained and reported by biotype.

Isoforms are grouped by NCBI `GeneID` first. The longest transcript per gene is clustered with MMseqs2 at 80% nucleotide identity and 80% coverage; every transcript inherits its representative's cluster. Train/validation/test are split by cluster, and the notebook asserts zero cross-split overlap for both GeneID and cluster ID.

## Models and evaluation
- Majority-class baseline.
- Interpretable logistic regression on length, GC fraction, and normalized 3-mer frequencies.
- Character 3–5-mer TF-IDF logistic regression; a small `C` grid is selected on validation AUPRC only.
- The final test set is evaluated once after refitting the selected model on train+validation.
- Test metrics: precision, recall, F1, AUROC, AUPRC, confusion matrix, and bootstrap 95% intervals. Validation-only seed sensitivity is reported for seeds 42, 43, and 44.
- Error analysis breaks down results by label, GFF3 biotype, length quartile, GC fraction, and individual uncertain errors.

## MMseqs2 threshold sensitivity
The notebook now tests identity thresholds of **70%, 75%, 80%, 85%, 90%, and 95%**, with coverage fixed at 80%. It reruns MMseqs2 on the same per-GeneID representative set, creates a threshold-specific grouped split, and prints:

1. A train/test leakage matrix showing shared clusters when each split is audited at each identity threshold.
2. A generalization table with split size, cluster count, own-threshold overlap, 70%-audit overlap, precision, recall, F1, AUROC, and AUPRC.

The model-selection choice (`C`) from the primary validation workflow is held fixed during this sensitivity analysis; thresholds are not tuned on test performance. The final manifest includes both result tables.

## Rerun in Google Colab
1. Open `04_ncbi_human_transcript_coding_status.ipynb` in Colab.
2. Run all cells from top to bottom. The first setup cell installs `ncbi-datasets-cli` and `mmseqs2` if needed.
3. The download may take time and requires internet access. The notebook caches the package under `ncbi_refseq_cache/`.
4. Set `MAX_MODEL_PER_CLASS = None` only after confirming the baseline runtime; the audit already covers all parsed eligible records.
5. The last cells write `transcript_coding_status_manifest.json` with counts, versions, source URL, split settings, zero-overlap assertions, the threshold leakage matrix, and threshold generalization results.

No result numbers are hard-coded in this README: run the notebook to generate them from the stated release and record the manifest with the notebook output.
