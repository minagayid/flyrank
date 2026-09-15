"""Human-readable validation labels and strict metric-run provenance checks."""

import hashlib
import json
import re


_SPLIT_DESCRIPTIONS = {
    "client_holdout": (
        "client holdout",
        "Entire anonymized clients are held out from training.",
    ),
    "stratified_row_holdout": (
        "stratified row holdout",
        "Fallback split is row-based and does not establish new-client generalization.",
    ),
}
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def build_run_provenance(
    *,
    feature_data_sha256: str,
    baseline_data_sha256: str,
    code_bundle_sha256: str,
    random_seed: int,
    split_strategy: str,
) -> dict[str, str | int]:
    """Build a reproducible identifier for the input data, split, and code."""
    payload: dict[str, str | int] = {
        "feature_data_sha256": feature_data_sha256,
        "baseline_data_sha256": baseline_data_sha256,
        "code_bundle_sha256": code_bundle_sha256,
        "random_seed": random_seed,
        "split_strategy": split_strategy,
    }
    if any(
        not isinstance(payload[key], str) or not _SHA256.fullmatch(payload[key])
        for key in ("feature_data_sha256", "baseline_data_sha256", "code_bundle_sha256")
    ):
        raise ValueError("Run provenance requires SHA-256 fingerprints for each input and code bundle.")
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise ValueError("Run provenance requires an integer random seed.")
    if split_strategy not in _SPLIT_DESCRIPTIONS:
        raise ValueError("Run provenance requires a recognized validation split strategy.")
    run_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**payload, "run_id": run_id}


def validation_style(results: dict) -> tuple[str, str]:
    """Describe the split recorded by training without overstating its scope."""
    strategy = results.get("split_strategy") if isinstance(results, dict) else None
    if not isinstance(strategy, str):
        strategy = None
    return _SPLIT_DESCRIPTIONS.get(
        strategy,
        ("unspecified", "The training output did not record a recognized split strategy."),
    )


def metric_provenance_error(results: dict) -> str | None:
    """Return why result metrics cannot be published, or None when verifiable."""
    if not isinstance(results, dict) or validation_style(results)[0] == "unspecified":
        return "Metrics are blocked because the result has no recognized validation split."
    provenance = results.get("run_provenance")
    if not isinstance(provenance, dict):
        return "Metrics are blocked until the result includes run provenance."
    try:
        expected = build_run_provenance(
            feature_data_sha256=provenance["feature_data_sha256"],
            baseline_data_sha256=provenance["baseline_data_sha256"],
            code_bundle_sha256=provenance["code_bundle_sha256"],
            random_seed=provenance["random_seed"],
            split_strategy=provenance["split_strategy"],
        )
    except (KeyError, TypeError, ValueError):
        return "Metrics are blocked because the run provenance is incomplete or invalid."
    if provenance != expected or results.get("split_strategy") != expected["split_strategy"]:
        return "Metrics are blocked because the run identifier does not match its data, code, seed, and split."
    return None


def require_metric_provenance(results: dict) -> None:
    """Stop report generation unless metrics are linked to a reproducible run."""
    error = metric_provenance_error(results)
    if error:
        raise ValueError(error)
