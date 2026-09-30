# CRISPR-Cas9 off-target ML study

This artifact adapts FlyRank's sequence-feature and grouped-validation ideas to public SITE-seq data.
It is a computational review aid, not a guide-design approval or experimental substitute.

- Rows: 6,868; intended guides: 9; off-target rows: 6,859
- Baseline AUROC/AUPRC: 1.000 / 1.000
- Grouped logistic AUROC/AUPRC: 1.000 / 1.000
- Grouped activity model Spearman rho: 0.186; top-5% enrichment: 8.71x
- Grouped logistic AUROC 95% bootstrap interval: [1.000, 1.000]
- Grouped logistic AUPRC 95% bootstrap interval: [1.000, 1.000]

## Reuse of the new FlyRank notebook ideas

1. Position-aware nucleotide features replace generic transcript k-mers.
2. Guide-grouped folds prevent the same intended guide from appearing in train and test.
3. A transparent mismatch baseline is reported beside the learned model.
4. The main ranking task predicts assay activity as well as reporting the simple ON/OFF sanity screen.
5. Bootstrap intervals and provenance are saved with the result, and biological limitations are explicit.

## Safety and interpretation

The score prioritizes off-target candidates for review. It does not search the genome, model chromatin or cell state, or establish that editing will occur. Any experimental program still needs an assembly-specific alignment/off-target workflow, independent review, and empirical validation.
