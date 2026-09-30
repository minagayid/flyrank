#!/usr/bin/env python3
"""Reproducible SITE-seq off-target risk study.

This study adapts FlyRank notebook 04's sequence modeling ideas to CRISPR-Cas9:
- sequence-derived features only
- guide-grouped out-of-fold evaluation (no guide appears in train and test)
- explicit mismatch/seed features and an interpretable baseline
- public data downloaded at runtime; no benchmark data is committed

It is a research/decision-support artifact, not a clinical or experimental protocol.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from scipy.stats import spearmanr

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "work" / "crispr_cache"
OUTPUT = ROOT / "outputs" / "crispr"
CACHE.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "site_seq_moesm86.xlsx": "https://raw.githubusercontent.com/dagrate/public_data_crisprCas9/main/data/site_seq/41592_2017_BFnmeth4284_MOESM86_ESM.xlsx",
}


def download(url: str, path: Path) -> str:
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_sequence(row: pd.Series) -> str:
    return "".join(str(row[i]).strip().upper() for i in range(1, 21))


def load_site_seq() -> tuple[pd.DataFrame, dict]:
    sha = {}
    frames = []
    for filename, url in SOURCES.items():
        path = CACHE / filename
        sha[filename] = download(url, path)
        book = pd.ExcelFile(path)
        for sheet in book.sheet_names:
            raw = pd.read_excel(path, sheet_name=sheet)
            cols = set(raw.columns)
            if "identity" not in cols or 1 not in cols or 20 not in cols:
                continue
            raw = raw.copy()
            raw["table"] = sheet.strip()
            raw["sequence"] = raw.apply(clean_sequence, axis=1)
            raw["identity"] = raw["identity"].astype(str).str.upper().str.strip()
            raw = raw[raw["identity"].isin(["ON", "OFF"])].copy()
            # The single ON motif in each table is the intended guide sequence.
            guide = raw.loc[raw.identity.eq("ON"), "sequence"]
            if len(guide) != 1:
                raise ValueError(f"Expected exactly one ON guide in {sheet}, found {len(guide)}")
            raw["guide_sequence"] = guide.iloc[0]
            raw["guide_group"] = raw["table"]
            raw["label"] = raw["identity"].eq("OFF").astype(int)
            if "_4nM CR" in raw.columns:
                raw["activity_4nM"] = pd.to_numeric(raw["_4nM CR"].replace("bd", 0), errors="coerce")
            else:
                raw["activity_4nM"] = np.nan
            raw["mismatch_vector"] = raw.apply(
                lambda r: [int(a != b) for a, b in zip(r["guide_sequence"], r["sequence"])], axis=1
            )
            frames.append(raw[["table", "guide_group", "sequence", "guide_sequence", "identity", "label", "activity_4nM", "mismatch_vector"]])
    data = pd.concat(frames, ignore_index=True)
    data["mismatch_count"] = data.mismatch_vector.map(sum)
    # Columns 13-20 are treated as the PAM-proximal seed window for this audit.
    data["seed_mismatch_count"] = data.mismatch_vector.map(lambda x: sum(x[12:20]))
    data["distal_mismatch_count"] = data.mismatch_vector.map(lambda x: sum(x[:12]))
    data["gc_fraction"] = data.sequence.map(lambda s: sum(c in "GC" for c in s) / 20)
    data["pam"] = data.sequence.map(lambda s: "")
    data["guide_gc_fraction"] = data.guide_sequence.map(lambda s: sum(c in "GC" for c in s) / 20)
    data["exact_match"] = data.mismatch_count.eq(0).astype(int)
    return data, {"source_sha256": sha, "source_urls": list(SOURCES.values())}


def feature_frame(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in data.iterrows():
        row = {
            "mismatch_count": r.mismatch_count,
            "seed_mismatch_count": r.seed_mismatch_count,
            "extended_seed_mismatch_count": sum(r.mismatch_vector[10:20]),
            "distal_mismatch_count": r.distal_mismatch_count,
            "gc_fraction": r.gc_fraction,
            "guide_gc_fraction": r.guide_gc_fraction,
        }
        row.update({f"mismatch_pos_{i+1:02d}": int(v) for i, v in enumerate(r.mismatch_vector)})
        rows.append(row)
    return pd.DataFrame(rows, index=data.index)


def nested_extended_seed_rank(mm: np.ndarray, y: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    """Tune the PAM-proximal window and weight inside each outer fold only."""
    outer = GroupKFold(n_splits=4)
    grid = [(start, weight) for start in [8, 9, 10, 11, 12] for weight in np.arange(1.0, 6.1, 0.5)]
    prediction = np.zeros(len(y), dtype=float)
    selections = []
    for train_ix, test_ix in outer.split(mm, y, groups):
        inner = GroupKFold(n_splits=3)
        best = None
        for start, weight in grid:
            scores = []
            for inner_train, inner_valid in inner.split(mm[train_ix], y[train_ix], groups[train_ix]):
                rank = -(mm[train_ix][inner_valid, :start].sum(axis=1) + weight * mm[train_ix][inner_valid, start:].sum(axis=1))
                scores.append(float(spearmanr(y[train_ix][inner_valid], rank).statistic))
            candidate = (float(np.nanmean(scores)), start, float(weight))
            if best is None or candidate[0] > best[0]:
                best = candidate
        _, start, weight = best
        prediction[test_ix] = -(mm[test_ix, :start].sum(axis=1) + weight * mm[test_ix, start:].sum(axis=1))
        selections.append({"extended_seed_start_position": int(start + 1), "extended_seed_weight": float(weight)})
    return prediction, selections


def bootstrap_ci(y: np.ndarray, score: np.ndarray, metric, seed: int = SEED, n: int = 1000) -> list[float]:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n):
        ix = rng.integers(0, len(y), len(y))
        if len(np.unique(y[ix])) < 2:
            continue
        values.append(metric(y[ix], score[ix]))
    return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def evaluate(y: np.ndarray, score: np.ndarray, threshold: float = 0.5) -> dict:
    pred = (score >= threshold).astype(int)
    return {
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "auroc": float(roc_auc_score(y, score)),
        "auprc": float(average_precision_score(y, score)),
        "confusion_matrix": confusion_matrix(y, pred).tolist(),
    }


def regression_metrics(y: np.ndarray, prediction: np.ndarray) -> dict:
    rho = float(spearmanr(y, prediction).statistic)
    top_n = max(1, int(np.ceil(0.05 * len(y))))
    top = np.argsort(-prediction)[:top_n]
    prevalence = float((y > 0).mean())
    top_rate = float((y[top] > 0).mean())
    return {
        "spearman_rho": rho,
        "top_5pct_nonzero_activity_rate": top_rate,
        "overall_nonzero_activity_rate": prevalence,
        "top_5pct_enrichment": float(top_rate / prevalence) if prevalence else None,
    }


def main() -> None:
    data, provenance = load_site_seq()
    X = feature_frame(data)
    y = data.label.to_numpy()
    groups = data.guide_group.to_numpy()
    cv = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEED)

    # Transparent baseline: every mismatch increases risk, seed mismatches count twice.
    baseline_raw = data.mismatch_count.to_numpy() + 2 * data.seed_mismatch_count.to_numpy()
    baseline_score = (baseline_raw - baseline_raw.min()) / max(1, baseline_raw.max() - baseline_raw.min())
    # Logistic regression keeps the position-specific feature effects inspectable.
    model = Pipeline([
        ("scale", StandardScaler()),
        ("logreg", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEED)),
    ])
    model_score = cross_val_predict(model, X, y, groups=groups, cv=cv, method="predict_proba")[:, 1]
    activity_mask = data.activity_4nM.notna().to_numpy()
    activity = data.loc[activity_mask, "activity_4nM"].to_numpy(dtype=float)
    activity_X = X.loc[activity_mask]
    activity_groups = groups[activity_mask]
    activity_mm = np.asarray(data.loc[activity_mask, "mismatch_vector"].tolist(), dtype=int)
    engineered_prediction, fold_selections = nested_extended_seed_rank(activity_mm, np.log1p(activity), activity_groups)
    activity_model = RandomForestRegressor(
        n_estimators=300, min_samples_leaf=5, max_features="sqrt", random_state=SEED, n_jobs=-1
    )
    activity_prediction = cross_val_predict(
        activity_model, activity_X, np.log1p(activity), groups=activity_groups,
        cv=GroupKFold(n_splits=4), method="predict"
    )
    activity_baseline = -baseline_raw[activity_mask].astype(float)
    activity_prediction_full = np.full(len(data), np.nan)
    activity_prediction_full[activity_mask] = engineered_prediction

    results = {
        "study": "SITE-seq guide-grouped off-target risk classification and activity ranking",
        "seed": SEED,
        "rows": int(len(data)),
        "guides": int(data.guide_group.nunique()),
        "on_target_rows": int((y == 0).sum()),
        "off_target_rows": int((y == 1).sum()),
        "activity_rows": int(activity_mask.sum()),
        "split": {
            "method": "StratifiedGroupKFold",
            "n_splits": 4,
            "group_key": "table / intended guide",
            "leakage_check": "Each workbook table/guide group is kept within one fold.",
        },
        "features": list(X.columns),
        "seed_definition": "mismatch positions 13-20 (1-indexed) are the PAM-proximal audit window; validate this convention against the chosen genome/assay before operational use.",
        "extended_seed_definition": "positions 11-20 are an extended PAM-proximal window; its start and weight are selected inside each outer training fold only.",
        "baseline": evaluate(y, baseline_score, threshold=0.5),
        "model": evaluate(y, model_score, threshold=0.5),
        "activity_target": "log1p(SITE-seq 4 nM cleavage signal; 'bd' mapped to 0)",
        "activity_baseline": regression_metrics(activity, activity_baseline),
        "activity_model": regression_metrics(activity, engineered_prediction),
        "activity_random_forest_comparison": regression_metrics(activity, np.expm1(activity_prediction)),
        "activity_model_selection": fold_selections,
        "model_auroc_ci95": bootstrap_ci(y, model_score, roc_auc_score),
        "model_auprc_ci95": bootstrap_ci(y, model_score, average_precision_score),
        "provenance": provenance,
        "limitations": [
            "SITE-seq is an empirical assay and the label is not a universal in-vivo activity truth.",
            "The benchmark covers a small set of guides and human loci; external generalization is unproven.",
            "This model ranks risk for review; it does not perform genome-wide alignment or certify specificity.",
            "Use a validated aligner/off-target tool, the correct reference assembly, cell context, and wet-lab checks before any biological decision.",
        ],
    }
    pred = (model_score >= 0.5).astype(int)
    out = data[["table", "sequence", "guide_sequence", "identity", "mismatch_count", "seed_mismatch_count", "gc_fraction"]].copy()
    out["baseline_risk"] = baseline_score
    out["model_off_target_risk"] = model_score
    out["activity_4nM"] = data["activity_4nM"].to_numpy()
    out["engineered_activity_rank_score"] = activity_prediction_full
    out["review_priority"] = pd.cut(model_score, [-0.01, 0.33, 0.66, 1.01], labels=["lower", "middle", "higher"])
    out.sort_values(["model_off_target_risk", "mismatch_count"], ascending=[False, True]).to_csv(OUTPUT / "site_seq_ranked_review.csv", index=False)
    (OUTPUT / "study_results.json").write_text(json.dumps(results, indent=2))
    summary = [
        "# CRISPR-Cas9 off-target ML study",
        "",
        "This artifact adapts FlyRank's sequence-feature and grouped-validation ideas to public SITE-seq data.",
        "It is a computational review aid, not a guide-design approval or experimental substitute.",
        "",
        f"- Rows: {results['rows']:,}; intended guides: {results['guides']}; off-target rows: {results['off_target_rows']:,}",
        f"- Baseline AUROC/AUPRC: {results['baseline']['auroc']:.3f} / {results['baseline']['auprc']:.3f}",
        f"- Grouped logistic AUROC/AUPRC: {results['model']['auroc']:.3f} / {results['model']['auprc']:.3f}",
        f"- Nested extended-seed activity ranker Spearman rho: {results['activity_model']['spearman_rho']:.3f}; top-5% enrichment: {results['activity_model']['top_5pct_enrichment']:.2f}x",
        f"- Legacy random-forest comparison Spearman rho: {results['activity_random_forest_comparison']['spearman_rho']:.3f}",
        f"- Grouped logistic AUROC 95% bootstrap interval: [{results['model_auroc_ci95'][0]:.3f}, {results['model_auroc_ci95'][1]:.3f}]",
        f"- Grouped logistic AUPRC 95% bootstrap interval: [{results['model_auprc_ci95'][0]:.3f}, {results['model_auprc_ci95'][1]:.3f}]",
        "",
        "## Reuse of the new FlyRank notebook ideas",
        "",
        "1. Position-aware nucleotide features replace generic transcript k-mers.",
        "2. An extended PAM-proximal mismatch feature is tuned only inside training folds.",
        "3. Guide-grouped folds prevent the same intended guide from appearing in train and test.",
        "4. The tuned ranker is reported beside the original mismatch baseline and legacy random forest.",
        "5. Bootstrap intervals and provenance are saved with the result, and biological limitations are explicit.",
        "",
        "## Safety and interpretation",
        "",
        "The score prioritizes off-target candidates for review. It does not search the genome, model chromatin or cell state, or establish that editing will occur. Any experimental program still needs an assembly-specific alignment/off-target workflow, independent review, and empirical validation.",
    ]
    (OUTPUT / "study_report.md").write_text("\n".join(summary) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
