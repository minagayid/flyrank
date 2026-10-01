# Human RefSeq transcript coding-status study

## Question and scope

In one pinned human RefSeq annotation snapshot, how well can nucleotide sequence features distinguish transcripts annotated with a coding sequence (CDS) from explicitly annotated noncoding transcripts?

This is a preliminary study of versioned human RefSeq NM_/NR_ transcripts on GRCh38.p14. It excludes predicted XM_/XR_ models, pseudogenes, unresolved labels, FLIP2 results, and variant information.

## Source and labels

- Source: NCBI human assembly GCF_000001405.40 (GRCh38.p14), annotation release GCF_000001405.40-RS_2025_08.
- Snapshot files: accession-versioned RNA FASTA, genomic GFF3, assembly report, and NCBI md5checksums.txt from the exact release directory.
- The notebook pins the exact NCBI MD5-list SHA-256. It verifies NCBI MD5 values and original-file SHA-256 values when Kaggle supplies compressed source files; when Kaggle expands them, it verifies pinned SHA-256 values for the decompressed payloads.
- Label coding when the versioned transcript is linked through GFF3 `transcript_id`/`Parent` attributes to a CDS feature on an assembled molecule in the assembly report.
- Label noncoding only when no CDS is present on those assembled molecules and the GFF3 feature or biotype explicitly describes a noncoding RNA.
- The assembled-molecule set includes chromosomes 1–22, X, Y, and mitochondrion; alternate placements are excluded.
- NM_/NR_ accession prefixes are a source-consistency check. Prefix disagreements, pseudogenes, ambiguous/unmatched annotation, missing or conflicting GeneIDs, invalid sequences, and conflicting duplicate accessions are excluded and counted.
- Labels describe this NCBI annotation snapshot; they are not experimental evidence of translation, expression, or biological function.

NCBI references: [annotation report](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Homo_sapiens/GCF_000001405.40-RS_2025_08/), [release FTP directory](https://ftp.ncbi.nlm.nih.gov/genomes/all/annotation_releases/9606/GCF_000001405.40-RS_2025_08/), [GFF3 format documentation](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/file-formats/annotation-files/about-ncbi-gff3/).

## Sampling and leakage control

The audit covers every parsed versioned NM_/NR_ record. The only transcript length floor is 20 nt, used to remove empty or malformed records while retaining legitimate short RNAs. Modeling is capped at 3,000 eligible records per label, sampled with seed 42.

MMseqs2 clusters every selected transcript, not one representative per gene. The split unit is the connected component formed by shared GeneID, exact sequence, or MMseqs2 cluster. At 80% identity and coverage, the notebook searches every pair of splits on both strands; any qualifying cross-split hit is added as a sequence-link between connected groups, then it repeats grouping, splitting, and searching. It fits models only after all three boundary searches return zero hits. The repair loop stops if it cannot add new links or ten rounds are insufficient. This search is heuristic: zero detected hits means no qualifying match under the stated settings, not proof that no similar sequence exists. A sensitivity analysis repeats grouping at 70%, 75%, 80%, 85%, 90%, and 95% identity. Similarity thresholds are methodological choices, not universal biological boundaries.

## Models and evaluation

1. Majority-class baseline.
2. Logistic regression on log length, GC fraction, and normalized 3-mer frequencies.
3. Character 3-5-mer TF-IDF logistic regression; regularization is selected by validation AUPRC only.

The primary held-out test split is evaluated after model selection; both fitted models and the majority baseline use train-plus-validation class prevalence/training data for test scoring. The notebook reports precision, recall, F1, AUROC, AUPRC, accuracy, balanced accuracy, confusion matrix, and confidence intervals from connected-component bootstrap resampling. Error summaries are broken down by label, GFF3 biotype, length, and GC content. Threshold sensitivity uses repeated descriptive test evaluations, carries forward the primary split's pairwise repair links at every threshold, and does not select the primary result. Sampling and point estimates are transcript-weighted, so genes with many isoforms can contribute more records.

These CPU-friendly models do not require a GPU; the study makes no GPU-training claim. External assembly validation and independent bioinformatics review remain pending. The checklist is in REVIEWER_CHECKLIST_TRANSCRIPT_CODING_STATUS.md.

## Observed Kaggle run

The completed CPU run on 2026-10-01 evaluated 1,180 held-out transcripts in 943 connected components. The majority baseline, length/GC/3-mer logistic model, and TF-IDF logistic model (C=4) had AUPRC 0.4856, 0.7695, and 0.7699 respectively; their F1 scores were 0.6537, 0.7338, and 0.7394. The two fitted models had overlapping 95% connected-component bootstrap intervals, so the small point-estimate differences do not establish a clear winner. The final 80% identity / 80% coverage boundary searches found zero qualifying hits after one repair round (10 initial hits, 9 links added). The repeated 70–95% identity sensitivity evaluations and subgroup error analysis are reported on the [study findings page](../docs/human-transcript-coding-status/).

Kaggle completed the analysis cells and produced aggregate outputs in the active session, but saving a version hit a notebook kernel concurrency error. The interactive run is therefore not yet a verified saved Kaggle version. The notebook source and aggregate findings are available here for review; do not treat the failed version save as persisted Kaggle output.

## Rerun

Run all cells in notebooks/04_ncbi_human_transcript_coding_status.ipynb in Kaggle or Colab. In Kaggle, attach the private dataset `RefSeq GRCh38 Transcript Inputs 2025-08` containing `refseq_human_transcript_inputs.zip`. Kaggle may automatically expand the ZIP, GZIP, or TAR.GZ contents; the notebook locates either the compressed files/archive or Kaggle's expanded source files and executable. The attached checksum list and expected source/binary hashes are pinned, so it can run with Internet disabled. The MMseqs2 archive or binary is verified before use. The notebook saves aggregate CSV files and `transcript_coding_status_manifest.json` under `outputs/transcript_coding_status/`.

The raw NCBI files and MMseqs2 archive are not committed to this repository.
