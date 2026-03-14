"""Train the baseline LightGBM point model for delivery lead time prediction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.config_utils import load_config


def validate_config(config: dict[str, Any]) -> None:
    """Validate model configuration before training starts."""
    required_top_level_keys = [
        "target_column",
        "data",
        "artifacts",
        "features",
        "training",
        "lightgbm_params",
        "evaluation",
    ]
    missing_keys = [key for key in required_top_level_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing model config keys: {missing_keys}")

    data_config = config["data"]
    for split_name in ["train_path", "val_path", "test_path"]:
        dataset_path = Path(data_config[split_name])
        if not dataset_path.exists():
            raise FileNotFoundError(
                f"Configured dataset for '{split_name}' was not found at '{dataset_path}'."
            )

    artifacts_dir = Path(config["artifacts"]["point_model_dir"])
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    clip_min_prediction = config["evaluation"]["clip_min_prediction"]
    if clip_min_prediction < 0:
        raise ValueError("clip_min_prediction must be non-negative.")


def load_datasets(config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Load the configured train, validation, and test datasets."""
    data_config = config["data"]
    datasets = {
        "train": pd.read_csv(data_config["train_path"]),
        "validation": pd.read_csv(data_config["val_path"]),
        "test": pd.read_csv(data_config["test_path"]),
    }
    return datasets


def validate_datasets(datasets: dict[str, pd.DataFrame], config: dict[str, Any]) -> None:
    """Validate that the processed datasets are non-empty and schema-consistent."""
    target_column = config["target_column"]
    categorical_columns = config["features"]["categorical"]

    schema_reference: list[str] | None = None
    for split_name, dataset in datasets.items():
        if dataset.empty:
            raise ValueError(f"The {split_name} dataset is empty.")

        if target_column not in dataset.columns:
            raise ValueError(
                f"Target column '{target_column}' is missing from the {split_name} dataset."
            )

        missing_categorical = [
            column for column in categorical_columns if column not in dataset.columns
        ]
        if missing_categorical:
            raise ValueError(
                f"Categorical columns missing from the {split_name} dataset: "
                f"{missing_categorical}"
            )

        current_schema = list(dataset.columns)
        if schema_reference is None:
            schema_reference = current_schema
        elif current_schema != schema_reference:
            raise ValueError(
                f"Dataset schema mismatch detected in the {split_name} dataset."
            )


def resolve_feature_columns(
    train_df: pd.DataFrame, config: dict[str, Any]
) -> tuple[list[str], list[str], list[str]]:
    """Resolve usable feature columns, split into categorical and numeric groups."""
    target_column = config["target_column"]
    exclude_columns = set(config["features"]["exclude_columns"])
    categorical_columns = config["features"]["categorical"]

    feature_columns = [
        column
        for column in train_df.columns
        if column != target_column and column not in exclude_columns
    ]
    if not feature_columns:
        raise ValueError("No usable feature columns remain after exclusions.")

    missing_categorical = [
        column for column in categorical_columns if column not in feature_columns
    ]
    if missing_categorical:
        raise ValueError(
            "Configured categorical columns are not available as training features: "
            f"{missing_categorical}"
        )

    numeric_columns = [
        column for column in feature_columns if column not in categorical_columns
    ]
    if not numeric_columns and not categorical_columns:
        raise ValueError("No numeric or categorical features remain for training.")

    return feature_columns, categorical_columns, numeric_columns


def build_preprocessor(
    categorical_columns: list[str], numeric_columns: list[str]
) -> ColumnTransformer:
    """Create the preprocessing transformer used by the model pipeline."""
    transformers: list[tuple[str, Pipeline, list[str]]] = []

    if numeric_columns:
        numeric_pipeline = Pipeline(
            steps=[("imputer", SimpleImputer(strategy="median"))]
        )
        transformers.append(("numeric", numeric_pipeline, numeric_columns))

    if categorical_columns:
        categorical_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                (
                    "encoder",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ),
            ]
        )
        transformers.append(("categorical", categorical_pipeline, categorical_columns))

    return ColumnTransformer(transformers=transformers)


def build_model_pipeline(
    config: dict[str, Any],
    categorical_columns: list[str],
    numeric_columns: list[str],
) -> Pipeline:
    """Build the preprocessing-plus-model pipeline for point prediction."""
    random_seed = config["training"]["random_seed"]
    lightgbm_params = dict(config["lightgbm_params"])
    lightgbm_params.update(
        {
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


def compute_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """Compute the core regression metrics used in this stage."""
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 6),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 6),
        "r2": round(float(r2_score(y_true, y_pred)), 6),
    }


def clip_predictions(predictions: np.ndarray, clip_min_prediction: float) -> np.ndarray:
    """Apply the configured lower bound to model predictions."""
    return np.maximum(predictions, clip_min_prediction)


def build_prediction_frame(
    df: pd.DataFrame,
    actual: pd.Series,
    predicted: np.ndarray,
    split_name: str,
) -> pd.DataFrame:
    """Build row-level prediction outputs with lightweight diagnostics."""
    prediction_df = pd.DataFrame(
        {
            "actual_lead_time_minutes": actual.to_numpy(),
            "predicted_lead_time_minutes": predicted,
            "abs_error": np.abs(actual.to_numpy() - predicted),
            "split": split_name,
        },
        index=df.index,
    )

    for optional_column in ["seller_category", "hour_of_day", "is_peak_hour"]:
        if optional_column in df.columns:
            prediction_df[optional_column] = df[optional_column].to_numpy()

    return prediction_df


def extract_feature_importance(model_pipeline: Pipeline) -> pd.DataFrame:
    """Extract gain-based feature importances from the fitted LightGBM model."""
    preprocessor: ColumnTransformer = model_pipeline.named_steps["preprocessor"]
    model: LGBMRegressor = model_pipeline.named_steps["model"]

    feature_names = preprocessor.get_feature_names_out()
    importance = model.booster_.feature_importance(importance_type="gain")

    feature_importance_df = pd.DataFrame(
        {
            "feature_name": feature_names,
            "importance": importance,
        }
    ).sort_values("importance", ascending=False, ignore_index=True)

    return feature_importance_df


def save_artifacts(
    model_pipeline: Pipeline,
    metrics: dict[str, Any],
    feature_importance_df: pd.DataFrame,
    val_predictions: pd.DataFrame,
    test_predictions: pd.DataFrame,
    config: dict[str, Any],
) -> Path:
    """Persist the trained model and all required Stage 3 artifacts."""
    artifacts_dir = Path(config["artifacts"]["point_model_dir"])
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model_pipeline, artifacts_dir / "model.pkl")
    (artifacts_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    feature_importance_df.to_csv(artifacts_dir / "feature_importance.csv", index=False)
    val_predictions.to_csv(artifacts_dir / "predictions_val.csv", index=False)
    test_predictions.to_csv(artifacts_dir / "predictions_test.csv", index=False)
    (artifacts_dir / "model_config_snapshot.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )

    return artifacts_dir


def main() -> None:
    """Train the baseline point-prediction model and save Stage 3 artifacts."""
    print("Running point-model training pipeline.")
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

    baseline_prediction = float(y_train.mean())
    baseline_val_pred = np.full(len(y_val), baseline_prediction)
    baseline_test_pred = np.full(len(y_test), baseline_prediction)

    clip_min_prediction = config["evaluation"]["clip_min_prediction"]
    baseline_val_pred = clip_predictions(baseline_val_pred, clip_min_prediction)
    baseline_test_pred = clip_predictions(baseline_test_pred, clip_min_prediction)

    print("Training LightGBM baseline model.")
    model_pipeline = build_model_pipeline(config, categorical_columns, numeric_columns)
    model_pipeline.fit(x_train, y_train)

    val_pred = clip_predictions(model_pipeline.predict(x_val), clip_min_prediction)
    test_pred = clip_predictions(model_pipeline.predict(x_test), clip_min_prediction)

    metrics = {
        "baseline": {
            "validation": compute_metrics(y_val, baseline_val_pred),
            "test": compute_metrics(y_test, baseline_test_pred),
        },
        "lightgbm": {
            "validation": compute_metrics(y_val, val_pred),
            "test": compute_metrics(y_test, test_pred),
        },
    }

    val_predictions = build_prediction_frame(val_df, y_val, val_pred, "validation")
    test_predictions = build_prediction_frame(test_df, y_test, test_pred, "test")
    feature_importance_df = extract_feature_importance(model_pipeline)
    artifacts_dir = save_artifacts(
        model_pipeline,
        metrics,
        feature_importance_df,
        val_predictions,
        test_predictions,
        config,
    )

    print("Training complete.")
    print(f"Train rows: {len(train_df)}")
    print(f"Validation rows: {len(val_df)}")
    print(f"Test rows: {len(test_df)}")
    print(f"Number of features: {len(feature_columns)}")
    print(f"Baseline validation MAE: {metrics['baseline']['validation']['mae']}")
    print(f"Model validation MAE: {metrics['lightgbm']['validation']['mae']}")
    print(f"Artifacts saved to: {artifacts_dir}")


if __name__ == "__main__":
    main()
