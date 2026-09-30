# CRISPR-Cas9 off-target ML study

This artifact adapts FlyRank's sequence-feature and grouped-validation ideas to public SITE-seq data.
It is a computational review aid, not a guide-design approval or experimental substitute.

- Rows: 6,868; intended guides: 9; off-target rows: 6,859
- Baseline AUROC/AUPRC: 1.000 / 1.000
- Grouped logistic AUROC/AUPRC: 1.000 / 1.000
- Nested extended-seed activity ranker Spearman rho: 0.213; top-5% enrichment: 10.28x
- Legacy random-forest comparison Spearman rho: 0.191
- Grouped logistic AUROC 95% bootstrap interval: [1.000, 1.000]
- Grouped logistic AUPRC 95% bootstrap interval: [1.000, 1.000]

## Reuse of the new FlyRank notebook ideas

1. Position-aware nucleotide features replace generic transcript k-mers.
2. An extended PAM-proximal mismatch feature is tuned only inside training folds.
3. Guide-grouped folds prevent the same intended guide from appearing in train and test.
4. The tuned ranker is reported beside the original mismatch baseline and legacy random forest.
5. Bootstrap intervals and provenance are saved with the result, and biological limitations are explicit.

## Safety and interpretation

The score prioritizes off-target candidates for review. It does not search the genome, model chromatin or cell state, or establish that editing will occur. Any experimental program still needs an assembly-specific alignment/off-target workflow, independent review, and empirical validation.
