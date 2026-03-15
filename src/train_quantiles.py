"""Train quantile models for interval-aware delivery lead time prediction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_pinball_loss
from sklearn.pipeline import Pipeline

from src.config_utils import load_config
from src.train_model import (
    build_preprocessor,
    clip_predictions,
    extract_feature_importance,
    load_datasets,
    resolve_feature_columns,
    validate_datasets,
)

CANONICAL_INTERVAL_QUANTILES = [0.5, 0.9]


def validate_config(config: dict[str, Any]) -> None:
    """Validate quantile-stage configuration before training starts."""
    required_top_level_keys = [
        "target_column",
        "data",
        "artifacts",
        "features",
        "training",
        "lightgbm_params",
        "evaluation",
        "quantiles",
    ]
    missing_keys = [key for key in required_top_level_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing model config keys: {missing_keys}")

    for split_name in ["train_path", "val_path", "test_path"]:
        dataset_path = Path(config["data"][split_name])
        if not dataset_path.exists():
            raise FileNotFoundError(
                f"Configured dataset for '{split_name}' was not found at '{dataset_path}'."
            )

    quantiles = config["quantiles"]
    if not quantiles:
        raise ValueError("At least one quantile must be configured.")
    if any(q <= 0 or q >= 1 for q in quantiles):
        raise ValueError("Configured quantiles must all be between 0 and 1.")
    if len(set(quantiles)) != len(quantiles):
        raise ValueError("Configured quantiles must be unique.")

    missing_required = [q for q in CANONICAL_INTERVAL_QUANTILES if q not in quantiles]
    if missing_required:
        raise ValueError(
            f"Required quantiles are missing from config: {missing_required}"
        )

    clip_min_prediction = config["evaluation"]["clip_min_prediction"]
    if clip_min_prediction < 0:
        raise ValueError("clip_min_prediction must be non-negative.")

    artifacts_dir = Path(config["artifacts"]["quantile_model_dir"])
    artifacts_dir.mkdir(parents=True, exist_ok=True)


def build_quantile_pipeline(
    config: dict[str, Any],
    categorical_columns: list[str],
    numeric_columns: list[str],
    quantile: float,
) -> Pipeline:
    """Build a preprocessing-plus-LightGBM pipeline for a single quantile."""
    random_seed = config["training"]["random_seed"]
    lightgbm_params = dict(config["lightgbm_params"])
    lightgbm_params.update(
        {
            "objective": "quantile",
            "alpha": quantile,
            "random_state": random_seed,
            "feature_fraction_seed": random_seed,
            "bagging_seed": random_seed,
            "data_random_seed": random_seed,
        }
    )

    preprocessor = build_preprocessor(categorical_columns, numeric_columns)
    model = LGBMRegressor(**lightgbm_params)

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def quantile_label(quantile: float) -> str:
    """Convert a quantile float into a stable artifact label like q40 or q95."""
    return f"q{int(round(quantile * 100)):02d}"


def fit_quantile_models(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    config: dict[str, Any],
    categorical_columns: list[str],
    numeric_columns: list[str],
) -> dict[float, Pipeline]:
    """Fit one model per configured quantile."""
    models: dict[float, Pipeline] = {}
    quantiles = sorted(config["quantiles"])

    for quantile in quantiles:
        model_pipeline = build_quantile_pipeline(
            config=config,
            categorical_columns=categorical_columns,
            numeric_columns=numeric_columns,
            quantile=quantile,
        )
        model_pipeline.fit(x_train, y_train)
        models[quantile] = model_pipeline

    return models


def generate_interval_predictions(
    df: pd.DataFrame,
    actual: pd.Series,
    models: dict[float, Pipeline],
    config: dict[str, Any],
    split_name: str,
) -> tuple[pd.DataFrame, int]:
    """Generate quantile predictions, interval fields, and crossing corrections."""
    clip_min_prediction = config["evaluation"]["clip_min_prediction"]
    quantiles = sorted(config["quantiles"])
    prediction_columns = [f"pred_{quantile_label(q)}" for q in quantiles]
    prediction_matrix = np.column_stack(
        [
            clip_predictions(models[q].predict(df), clip_min_prediction)
            for q in quantiles
        ]
    )

    crossing_corrections = 0
    if config["evaluation"].get("enforce_monotonic_quantiles", False):
        corrected_matrix = np.maximum.accumulate(prediction_matrix, axis=1)
        row_changed_mask = np.any(corrected_matrix != prediction_matrix, axis=1)
        crossing_corrections = int(row_changed_mask.sum())
        prediction_matrix = corrected_matrix

    interval_df = pd.DataFrame(prediction_matrix, columns=prediction_columns, index=df.index)
    interval_df.insert(0, "actual_lead_time_minutes", actual.to_numpy())
    interval_df["split"] = split_name
    interval_df["interval_lower"] = interval_df[f"pred_{quantile_label(0.5)}"]
    interval_df["interval_upper"] = interval_df[f"pred_{quantile_label(0.9)}"]
    interval_df["interval_width"] = (
        interval_df["interval_upper"] - interval_df["interval_lower"]
    )
    interval_df["is_late_vs_upper"] = (
        interval_df["actual_lead_time_minutes"] > interval_df["interval_upper"]
    )
    interval_df["is_within_interval"] = (
        (interval_df["interval_lower"] <= interval_df["actual_lead_time_minutes"])
        & (interval_df["actual_lead_time_minutes"] <= interval_df["interval_upper"])
    )

    for optional_column in [
        "seller_category",
        "hour_of_day",
        "is_peak_hour",
        "trip_distance_km",
    ]:
        if optional_column in df.columns:
            interval_df[optional_column] = df[optional_column].to_numpy()

    return interval_df, crossing_corrections


def compute_interval_metrics(
    actual: pd.Series, interval_df: pd.DataFrame, quantiles: list[float]
) -> dict[str, float]:
    """Compute interval-quality and quantile-calibration metrics."""
    actual_array = actual.to_numpy()

    metrics = {
        "coverage_q50_q90": round(float(interval_df["is_within_interval"].mean()), 6),
        "avg_interval_width_q50_q90": round(
            float(interval_df["interval_width"].mean()), 6
        ),
        "late_rate_vs_q90": round(float(interval_df["is_late_vs_upper"].mean()), 6),
    }

    for quantile in quantiles:
        prediction_column = f"pred_{quantile_label(quantile)}"
        predictions = interval_df[prediction_column].to_numpy()
        metrics[f"pinball_loss_{quantile_label(quantile)}"] = round(
            float(mean_pinball_loss(actual_array, predictions, alpha=quantile)), 6
        )
        metrics[f"calibration_{quantile_label(quantile)}"] = round(
            float(np.mean(actual_array <= predictions)), 6
        )

    return metrics


def save_artifacts(
    models: dict[float, Pipeline],
    metrics: dict[str, Any],
    val_predictions: pd.DataFrame,
    test_predictions: pd.DataFrame,
    feature_importances: dict[float, pd.DataFrame],
    config: dict[str, Any],
) -> Path:
    """Persist Stage 4 models, metrics, predictions, and importances."""
    artifacts_dir = Path(config["artifacts"]["quantile_model_dir"])
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    for quantile, model in models.items():
        joblib.dump(model, artifacts_dir / f"{quantile_label(quantile)}_model.pkl")
    (artifacts_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    val_predictions.to_csv(artifacts_dir / "interval_predictions_val.csv", index=False)
    test_predictions.to_csv(
        artifacts_dir / "interval_predictions_test.csv", index=False
    )
    for quantile, importance_df in feature_importances.items():
        importance_df.to_csv(
            artifacts_dir / f"feature_importance_{quantile_label(quantile)}.csv",
            index=False,
        )

    return artifacts_dir


def main() -> None:
    """Train configured quantile models and save interval artifacts."""
    print("Running quantile-model training pipeline.")
    config = load_config("config/model_config.yaml")
    validate_config(config)

    random_seed = config["training"]["random_seed"]
    np.random.seed(random_seed)

    print("Loading processed datasets.")
    datasets = load_datasets(config)
    validate_datasets(datasets, config)

    train_df = datasets["train"]
    val_df = datasets["validation"]
    test_df = datasets["test"]
    target_column = config["target_column"]

    feature_columns, categorical_columns, numeric_columns = resolve_feature_columns(
        train_df, config
    )

    x_train = train_df[feature_columns]
    y_train = train_df[target_column]
    x_val = val_df[feature_columns]
    y_val = val_df[target_column]
    x_test = test_df[feature_columns]
    y_test = test_df[target_column]
    quantiles = sorted(config["quantiles"])

    print("Training quantile models.")
    models = fit_quantile_models(
        x_train=x_train,
        y_train=y_train,
        config=config,
        categorical_columns=categorical_columns,
        numeric_columns=numeric_columns,
    )

    val_predictions, val_crossing_corrections = generate_interval_predictions(
        df=x_val,
        actual=y_val,
        models=models,
        config=config,
        split_name="validation",
    )
    test_predictions, test_crossing_corrections = generate_interval_predictions(
        df=x_test,
        actual=y_test,
        models=models,
        config=config,
        split_name="test",
    )

    metrics = {
        "validation": compute_interval_metrics(y_val, val_predictions, quantiles),
        "test": compute_interval_metrics(y_test, test_predictions, quantiles),
        "quantile_crossing_corrections": {
            "validation": val_crossing_corrections,
            "test": test_crossing_corrections,
        },
    }

    feature_importances = {
        quantile: extract_feature_importance(models[quantile]) for quantile in quantiles
    }

    artifacts_dir = save_artifacts(
        models=models,
        metrics=metrics,
        val_predictions=val_predictions,
        test_predictions=test_predictions,
        feature_importances=feature_importances,
        config=config,
    )

    print("Quantile training complete.")
    print(f"Train rows: {len(train_df)}")
    print(f"Validation rows: {len(val_df)}")
    print(f"Test rows: {len(test_df)}")
    print(f"Resolved numeric features: {numeric_columns}")
    print(f"Resolved categorical features: {categorical_columns}")
    print(f"Trained quantiles: {quantiles}")
    print(f"Validation coverage: {metrics['validation']['coverage_q50_q90']}")
    print(
        "Validation interval width: "
        f"{metrics['validation']['avg_interval_width_q50_q90']}"
    )
    print(f"Validation late rate: {metrics['validation']['late_rate_vs_q90']}")
    print(f"Test coverage: {metrics['test']['coverage_q50_q90']}")
    print(f"Test interval width: {metrics['test']['avg_interval_width_q50_q90']}")
    print(f"Test late rate: {metrics['test']['late_rate_vs_q90']}")
    print(
        "Quantile crossing corrections: "
        f"validation={val_crossing_corrections}, test={test_crossing_corrections}"
    )
    print(f"Artifacts saved to: {artifacts_dir}")


if __name__ == "__main__":
    main()
