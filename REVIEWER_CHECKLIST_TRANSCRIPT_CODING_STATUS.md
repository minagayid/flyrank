# Bioinformatics reviewer checklist

## Question and scope

- [ ] Confirm the question is limited to sequence prediction of annotated coding status in human RefSeq transcripts.
- [ ] Confirm the fixed scope is GCF_000001405.40 / GRCh38.p14 / GCF_000001405.40-RS_2025_08.
- [ ] Confirm FLIP2 results and variant information are not mixed into this study.

## Source and labels

- [ ] Check that the RNA FASTA, genomic GFF3, assembly report, and checksum list come from the exact NCBI release directory.
- [ ] Confirm the exact NCBI checksum-list SHA-256 is pinned, the original NCBI MD5 values are checked when compressed files are available, and Kaggle-expanded payloads are checked against pinned SHA-256 values.
- [ ] Review the versioned NM_/NR_ accession match between FASTA and GFF3 and confirm GFF3 seqids are restricted to the assembly-report assembled molecules (chromosomes 1–22, X, Y, and mitochondrion).
- [ ] Confirm a coding label requires CDS evidence.
- [ ] Confirm a noncoding label requires no CDS plus an explicit noncoding feature or biotype.
- [ ] Review the counts for unmatched, ambiguous, pseudogene, prefix-disagreement, missing-GeneID, invalid-sequence, and duplicate-accession records.
- [ ] Confirm XM_/XR_ predicted models and unresolved records are excluded.
- [ ] Review NCBI data-use terms before redistributing source files.

## Sampling and leakage

- [ ] Confirm the audit covers the full parsed accession set before the modeling cap.
- [ ] Confirm the 20 nt rule is only a malformed/empty-sequence floor and short RNA classes remain eligible.
- [ ] Confirm class sampling is reproducible and capped at 3,000 eligible records per label.
- [ ] Confirm every selected transcript is clustered and all transcripts for one GeneID are kept together.
- [ ] Confirm exact-sequence matches and MMseqs2 clusters are joined into connected components before splitting.
- [ ] Confirm zero GeneID, exact-sequence, cluster, and component overlap across train, validation, and test.
- [ ] Review the iterative two-strand MMseqs2 all-vs-all checks across each split boundary, including the aggregate repair history; confirm detected sequence links are added to connected groups and final searches return zero hits. Interpret zero detected hits as conditional on the search settings, not an exhaustive homology proof.
- [ ] Confirm the 70%-95% identity sensitivity splits at fixed 80% coverage retain the primary pairwise repair links, then interpret the results as threshold sensitivity, not a universal cutoff.

## Modeling and interpretation

- [ ] Confirm preprocessing and regularization selection use training and validation data only.
- [ ] Compare the majority baseline, interpretable 3-mer model, and TF-IDF model on the same primary split.
- [ ] Review held-out metrics, denominators, confusion matrix, and connected-component bootstrap intervals.
- [ ] Review aggregate error patterns by label, biotype, length, and GC content.
- [ ] Confirm the repeated threshold sweep is described as descriptive test evaluation and does not choose the primary model.
- [ ] Confirm transcript-level sampling and transcript-weighted point estimates are stated as a limitation when genes have multiple isoforms.
- [ ] Treat results as annotation-snapshot classification, not evidence of biological translation or clinical validity.
- [ ] Require an independent chromosome/assembly test before stronger generalization claims.
