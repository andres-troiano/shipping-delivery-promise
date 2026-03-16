"""Evaluate buyer-facing delivery promise policies from quantile predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config_utils import load_config


def quantile_to_column_name(quantile: float) -> str:
    """Map a quantile value to its Stage 4 prediction column name."""
    return f"pred_q{int(round(quantile * 100)):02d}"


def validate_config(config: dict[str, Any]) -> None:
    """Validate policy-evaluation configuration and required files."""
    required_top_level_keys = ["artifacts", "policy_evaluation"]
    missing_keys = [key for key in required_top_level_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing model config keys: {missing_keys}")

    policy_config = config["policy_evaluation"]
    for key in ["validation_predictions_path", "test_predictions_path", "policies"]:
        if key not in policy_config:
            raise ValueError(f"Missing policy evaluation config key: {key}")

    for split_name, path_key in [
        ("validation", "validation_predictions_path"),
        ("test", "test_predictions_path"),
    ]:
        prediction_path = Path(policy_config[path_key])
        if not prediction_path.exists():
            raise FileNotFoundError(
                f"{split_name.capitalize()} prediction file not found at '{prediction_path}'."
            )

    policies = policy_config["policies"]
    if not policies:
        raise ValueError("At least one policy must be configured.")

    for policy in policies:
        if "name" not in policy or "lower_quantile" not in policy or "upper_quantile" not in policy:
            raise ValueError(
                "Each policy must define name, lower_quantile, and upper_quantile."
            )
        if policy["lower_quantile"] >= policy["upper_quantile"]:
            raise ValueError(
                f"Policy '{policy['name']}' must have lower_quantile < upper_quantile."
            )

    policy_dir = Path(config["artifacts"]["policy_analysis_dir"])
    policy_dir.mkdir(parents=True, exist_ok=True)


def load_prediction_datasets(config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Load Stage 4 interval prediction artifacts for validation and test."""
    policy_config = config["policy_evaluation"]
    return {
        "validation": pd.read_csv(policy_config["validation_predictions_path"]),
        "test": pd.read_csv(policy_config["test_predictions_path"]),
    }


def validate_prediction_datasets(datasets: dict[str, pd.DataFrame]) -> None:
    """Validate prediction files contain the minimum required columns."""
    required_columns = {"actual_lead_time_minutes", "split"}
    schema_reference: list[str] | None = None

    for split_name, dataset in datasets.items():
        if dataset.empty:
            raise ValueError(f"The {split_name} prediction dataset is empty.")

        missing_columns = required_columns - set(dataset.columns)
        if missing_columns:
            raise ValueError(
                f"The {split_name} prediction dataset is missing columns: "
                f"{sorted(missing_columns)}"
            )

        current_schema = list(dataset.columns)
        if schema_reference is None:
            schema_reference = current_schema
        elif current_schema != schema_reference:
            raise ValueError(
                f"Prediction schema mismatch detected in the {split_name} dataset."
            )


def resolve_valid_policies(
    config: dict[str, Any], available_columns: list[str]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Keep only policies whose required quantile columns exist."""
    valid_policies: list[dict[str, Any]] = []
    skipped_policies: dict[str, str] = {}

    for policy in config["policy_evaluation"]["policies"]:
        lower_column = quantile_to_column_name(policy["lower_quantile"])
        upper_column = quantile_to_column_name(policy["upper_quantile"])

        missing_columns = [
            column for column in [lower_column, upper_column] if column not in available_columns
        ]
        if missing_columns:
            skipped_policies[policy["name"]] = (
                f"missing column(s): {', '.join(sorted(missing_columns))}"
            )
            continue

        valid_policies.append(
            {
                **policy,
                "lower_column": lower_column,
                "upper_column": upper_column,
            }
        )

    if not valid_policies:
        raise ValueError("No valid policies remain after checking available quantile columns.")

    return valid_policies, skipped_policies


def evaluate_policy_rows(
    dataset: pd.DataFrame, policy: dict[str, Any]
) -> tuple[pd.DataFrame, int]:
    """Build row-level promise intervals and derived flags for a single policy."""
    columns_needed = [
        "actual_lead_time_minutes",
        policy["lower_column"],
        policy["upper_column"],
    ]
    row_df = dataset.loc[:, columns_needed].dropna().copy()

    row_df = row_df.rename(
        columns={
            policy["lower_column"]: "promise_start",
            policy["upper_column"]: "promise_end",
        }
    )
    row_df["policy_name"] = policy["name"]

    invalid_order_mask = row_df["promise_end"] < row_df["promise_start"]
    corrections = int(invalid_order_mask.sum())
    row_df.loc[invalid_order_mask, "promise_end"] = row_df.loc[
        invalid_order_mask, "promise_start"
    ]

    row_df["interval_width"] = row_df["promise_end"] - row_df["promise_start"]
    row_df["is_late"] = row_df["actual_lead_time_minutes"] > row_df["promise_end"]
    row_df["is_within_interval"] = (
        (row_df["promise_start"] <= row_df["actual_lead_time_minutes"])
        & (row_df["actual_lead_time_minutes"] <= row_df["promise_end"])
    )
    row_df["is_early_relative_to_start"] = (
        row_df["actual_lead_time_minutes"] < row_df["promise_start"]
    )

    return row_df, corrections


def summarize_policy_metrics(
    row_df: pd.DataFrame, policy: dict[str, Any], corrections: int
) -> dict[str, Any]:
    """Aggregate row-level policy outcomes into a metrics record."""
    return {
        "policy_name": policy["name"],
        "lower_quantile": policy["lower_quantile"],
        "upper_quantile": policy["upper_quantile"],
        "avg_interval_width": round(float(row_df["interval_width"].mean()), 6),
        "late_delivery_rate": round(float(row_df["is_late"].mean()), 6),
        "coverage": round(float(row_df["is_within_interval"].mean()), 6),
        "early_before_start_rate": round(
            float(row_df["is_early_relative_to_start"].mean()), 6
        ),
        "avg_promise_start": round(float(row_df["promise_start"].mean()), 6),
        "avg_promise_end": round(float(row_df["promise_end"].mean()), 6),
        "n_rows_used": int(len(row_df)),
        "order_corrections": corrections,
    }


def add_policy_rank_columns(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Add rank and Pareto-efficiency convenience columns."""
    metrics_df = metrics_df.copy()
    metrics_df["late_rate_rank"] = (
        metrics_df["late_delivery_rate"].rank(method="dense", ascending=True).astype(int)
    )
    metrics_df["width_rank"] = (
        metrics_df["avg_interval_width"].rank(method="dense", ascending=True).astype(int)
    )

    pareto_flags: list[bool] = []
    for _, candidate in metrics_df.iterrows():
        dominated = (
            (metrics_df["avg_interval_width"] <= candidate["avg_interval_width"])
            & (metrics_df["late_delivery_rate"] <= candidate["late_delivery_rate"])
            & (
                (metrics_df["avg_interval_width"] < candidate["avg_interval_width"])
                | (
                    metrics_df["late_delivery_rate"]
                    < candidate["late_delivery_rate"]
                )
            )
        ).any()
        pareto_flags.append(not dominated)

    metrics_df["pareto_efficient"] = pareto_flags
    return metrics_df.sort_values(
        ["late_delivery_rate", "avg_interval_width"], ascending=[True, True]
    ).reset_index(drop=True)


def evaluate_policies_for_split(
    dataset: pd.DataFrame, policies: list[dict[str, Any]]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate all valid policies on one split."""
    metrics_records: list[dict[str, Any]] = []
    row_level_frames: list[pd.DataFrame] = []

    for policy in policies:
        row_df, corrections = evaluate_policy_rows(dataset, policy)
        metrics_records.append(summarize_policy_metrics(row_df, policy, corrections))
        row_level_frames.append(row_df)

    metrics_df = add_policy_rank_columns(pd.DataFrame(metrics_records))
    row_level_df = pd.concat(row_level_frames, ignore_index=True)
    return metrics_df, row_level_df


def create_tradeoff_plot(metrics_df: pd.DataFrame, config: dict[str, Any], output_path: Path) -> None:
    """Create the validation trade-off plot of width versus late rate."""
    plot_config = config["policy_evaluation"]["plot"]
    figsize = tuple(plot_config.get("figsize", [8, 6]))

    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(metrics_df["avg_interval_width"], metrics_df["late_delivery_rate"])
    ax.set_title("Policy Trade-off: Interval Width vs Late Delivery Rate")
    ax.set_xlabel("Average interval width")
    ax.set_ylabel("Late delivery rate")
    ax.grid(True, alpha=0.3)

    if plot_config.get("annotate_points", True):
        for _, row in metrics_df.iterrows():
            ax.annotate(
                row["policy_name"],
                (row["avg_interval_width"], row["late_delivery_rate"]),
                xytext=(5, 5),
                textcoords="offset points",
            )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def select_reference_policy(metrics_df: pd.DataFrame, config: dict[str, Any]) -> str:
    """Select a reference policy using the configured validation heuristic."""
    selection_config = config["policy_evaluation"]["selection"]
    max_late_delivery_rate = selection_config["max_late_delivery_rate"]
    eligible = metrics_df.loc[
        metrics_df["late_delivery_rate"] <= max_late_delivery_rate
    ].copy()

    if not eligible.empty:
        chosen = eligible.sort_values(
            ["avg_interval_width", "late_delivery_rate"], ascending=[True, True]
        ).iloc[0]
        return str(chosen["policy_name"])

    fallback = selection_config.get("fallback", "lowest_late_rate")
    if fallback != "lowest_late_rate":
        raise ValueError(f"Unsupported fallback selection rule: {fallback}")

    chosen = metrics_df.sort_values(
        ["late_delivery_rate", "avg_interval_width"], ascending=[True, True]
    ).iloc[0]
    return str(chosen["policy_name"])


def save_artifacts(
    val_metrics_df: pd.DataFrame,
    test_metrics_df: pd.DataFrame,
    test_policy_predictions_df: pd.DataFrame,
    summary: dict[str, Any],
    config: dict[str, Any],
) -> Path:
    """Persist Stage 5 tables, plot, and summary."""
    output_dir = Path(config["artifacts"]["policy_analysis_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    val_metrics_df.to_csv(output_dir / "policy_metrics_val.csv", index=False)
    test_metrics_df.to_csv(output_dir / "policy_metrics_test.csv", index=False)
    test_policy_predictions_df.to_csv(
        output_dir / "policy_predictions_test.csv", index=False
    )
    create_tradeoff_plot(val_metrics_df, config, output_dir / "tradeoff_plot_val.png")
    (output_dir / "policy_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    return output_dir


def main() -> None:
    """Evaluate configured delivery promise policies from quantile predictions."""
    print("Running policy evaluation pipeline.")
    config = load_config("config/model_config.yaml")
    validate_config(config)

    print("Loading Stage 4 prediction artifacts.")
    datasets = load_prediction_datasets(config)
    validate_prediction_datasets(datasets)

    valid_policies, skipped_policies = resolve_valid_policies(
        config, list(datasets["validation"].columns)
    )

    print("Evaluating policies on validation and test splits.")
    val_metrics_df, _ = evaluate_policies_for_split(datasets["validation"], valid_policies)
    test_metrics_df, test_policy_predictions_df = evaluate_policies_for_split(
        datasets["test"], valid_policies
    )

    reference_policy = select_reference_policy(val_metrics_df, config)
    summary = {
        "evaluated_policies": val_metrics_df["policy_name"].tolist(),
        "skipped_policies": skipped_policies,
        "reference_policy": reference_policy,
        "validation_metrics": val_metrics_df.set_index("policy_name").to_dict(
            orient="index"
        ),
        "test_metrics": test_metrics_df.set_index("policy_name").to_dict(
            orient="index"
        ),
    }

    output_dir = save_artifacts(
        val_metrics_df=val_metrics_df,
        test_metrics_df=test_metrics_df,
        test_policy_predictions_df=test_policy_predictions_df[
            [
                "policy_name",
                "actual_lead_time_minutes",
                "promise_start",
                "promise_end",
                "interval_width",
                "is_late",
                "is_within_interval",
            ]
        ],
        summary=summary,
        config=config,
    )

    print("Policy evaluation complete.")
    print(f"Validation rows: {len(datasets['validation'])}")
    print(f"Test rows: {len(datasets['test'])}")
    print(f"Evaluated policies: {val_metrics_df['policy_name'].tolist()}")
    print(f"Skipped policies: {skipped_policies}")
    print(f"Reference policy: {reference_policy}")
    print(
        "Validation trade-off points: "
        f"{val_metrics_df[['policy_name', 'avg_interval_width', 'late_delivery_rate']].to_dict(orient='records')}"
    )
    print(
        "Test trade-off points: "
        f"{test_metrics_df[['policy_name', 'avg_interval_width', 'late_delivery_rate']].to_dict(orient='records')}"
    )
    print(f"Artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()
