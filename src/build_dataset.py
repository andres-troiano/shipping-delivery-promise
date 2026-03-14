"""Build a proxy delivery lead-time dataset from taxi trips and synthetic features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config_utils import load_config

REQUIRED_TRANSPORT_COLUMNS = [
    "pickup_datetime",
    "dropoff_datetime",
    "trip_duration",
    "pickup_latitude",
    "pickup_longitude",
    "dropoff_latitude",
    "dropoff_longitude",
]


def validate_config(config: dict[str, Any]) -> None:
    """Validate required configuration fields before running the pipeline."""
    raw_dataset_path = Path(config["raw_trip_dataset_path"])
    if not raw_dataset_path.exists():
        raise FileNotFoundError(
            f"Raw dataset not found at '{raw_dataset_path}'. "
            "Expected Kaggle NYC Taxi train data."
        )

    sample_size = config["sample_size"]
    if sample_size <= 0:
        raise ValueError("Configuration error: sample_size must be greater than 0.")

    split_config = config["split"]
    split_sum = (
        split_config["train_frac"]
        + split_config["val_frac"]
        + split_config["test_frac"]
    )
    if not np.isclose(split_sum, 1.0, atol=1e-9):
        raise ValueError("Configuration error: split fractions must sum to 1.")

    seller_category_probs = config["synthetic"]["seller_category_probs"]
    prob_sum = sum(seller_category_probs.values())
    if not np.isclose(prob_sum, 1.0, atol=1e-9):
        raise ValueError(
            "Configuration error: seller category probabilities must sum to 1."
        )


def load_raw_dataset(raw_dataset_path: Path) -> pd.DataFrame:
    """Load the raw NYC taxi dataset with the columns required by the prototype."""
    return pd.read_csv(
        raw_dataset_path,
        usecols=REQUIRED_TRANSPORT_COLUMNS,
        parse_dates=["pickup_datetime", "dropoff_datetime"],
    )


def drop_missing_transport_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove rows with missing values in required transport columns."""
    before = len(df)
    cleaned = df.dropna(subset=REQUIRED_TRANSPORT_COLUMNS).copy()
    dropped = before - len(cleaned)
    return cleaned, dropped


def filter_transport_rows(
    df: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply duration and geographic validity filters."""
    filter_stats: dict[str, int] = {}

    duration_filter = config["transport_filter"]
    duration_mask = df["trip_duration"].between(
        duration_filter["min_duration_seconds"],
        duration_filter["max_duration_seconds"],
    )
    filter_stats["rows_dropped_duration_filter"] = int((~duration_mask).sum())
    df = df.loc[duration_mask].copy()

    geo_filter = config["geo_filter"]
    pickup_lat_ok = df["pickup_latitude"].between(
        geo_filter["min_lat"], geo_filter["max_lat"]
    )
    dropoff_lat_ok = df["dropoff_latitude"].between(
        geo_filter["min_lat"], geo_filter["max_lat"]
    )
    pickup_lon_ok = df["pickup_longitude"].between(
        geo_filter["min_lon"], geo_filter["max_lon"]
    )
    dropoff_lon_ok = df["dropoff_longitude"].between(
        geo_filter["min_lon"], geo_filter["max_lon"]
    )
    geo_mask = pickup_lat_ok & dropoff_lat_ok & pickup_lon_ok & dropoff_lon_ok
    filter_stats["rows_dropped_geo_filter"] = int((~geo_mask).sum())
    df = df.loc[geo_mask].copy()

    return df, filter_stats


def haversine_distance_km(
    pickup_latitude: pd.Series,
    pickup_longitude: pd.Series,
    dropoff_latitude: pd.Series,
    dropoff_longitude: pd.Series,
) -> np.ndarray:
    """Compute haversine distance in kilometers for vectorized coordinate arrays."""
    earth_radius_km = 6371.0

    pickup_lat_rad = np.radians(pickup_latitude.to_numpy())
    pickup_lon_rad = np.radians(pickup_longitude.to_numpy())
    dropoff_lat_rad = np.radians(dropoff_latitude.to_numpy())
    dropoff_lon_rad = np.radians(dropoff_longitude.to_numpy())

    delta_lat = dropoff_lat_rad - pickup_lat_rad
    delta_lon = dropoff_lon_rad - pickup_lon_rad

    a = (
        np.sin(delta_lat / 2.0) ** 2
        + np.cos(pickup_lat_rad)
        * np.cos(dropoff_lat_rad)
        * np.sin(delta_lon / 2.0) ** 2
    )
    c = 2.0 * np.arcsin(np.sqrt(a))
    return earth_radius_km * c


def compute_transport_features(
    df: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, int]:
    """Create transport-duration and trip-distance features and filter tiny trips."""
    df = df.copy()
    df["delivery_duration_minutes"] = df["trip_duration"] / 60.0
    df["trip_distance_km"] = haversine_distance_km(
        pickup_latitude=df["pickup_latitude"],
        pickup_longitude=df["pickup_longitude"],
        dropoff_latitude=df["dropoff_latitude"],
        dropoff_longitude=df["dropoff_longitude"],
    )

    min_trip_distance_km = config["distance_filter"]["min_trip_distance_km"]
    distance_mask = df["trip_distance_km"] >= min_trip_distance_km
    rows_dropped_distance_filter = int((~distance_mask).sum())
    df = df.loc[distance_mask].copy()
    return df, rows_dropped_distance_filter


def deterministic_subsample(
    df: pd.DataFrame, sample_size: int, random_seed: int
) -> pd.DataFrame:
    """Deterministically subsample the cleaned transport dataset if needed."""
    if len(df) <= sample_size:
        return df.copy()

    sampled = df.sample(n=sample_size, random_state=random_seed).copy()
    return sampled.reset_index(drop=True)


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive interpretable temporal features from pickup time."""
    df = df.copy()
    pickup_dt = df["pickup_datetime"]
    df["hour_of_day"] = pickup_dt.dt.hour
    df["day_of_week"] = pickup_dt.dt.dayofweek
    df["month"] = pickup_dt.dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    peak_mask = df["hour_of_day"].between(11, 14) | df["hour_of_day"].between(18, 21)
    df["is_peak_hour"] = peak_mask.astype(int)
    return df


def generate_synthetic_features(
    df: pd.DataFrame, config: dict[str, Any], rng: np.random.Generator
) -> pd.DataFrame:
    """Generate seller, order, and operational synthetic variables."""
    df = df.copy()
    synthetic_config = config["synthetic"]
    n_rows = len(df)

    seller_category_probs = synthetic_config["seller_category_probs"]
    seller_categories = list(seller_category_probs.keys())
    probabilities = np.array(list(seller_category_probs.values()), dtype=float)
    seller_category = rng.choice(seller_categories, size=n_rows, p=probabilities)
    df["seller_category"] = seller_category

    seller_reliability_low, seller_reliability_high = synthetic_config[
        "seller_reliability_range"
    ]
    df["seller_reliability"] = rng.uniform(
        seller_reliability_low, seller_reliability_high, size=n_rows
    )

    order_size_low, order_size_high = synthetic_config["order_size_range"]
    df["order_size"] = rng.integers(order_size_low, order_size_high + 1, size=n_rows)
    df["priority_flag"] = (
        rng.random(n_rows) < synthetic_config["priority_probability"]
    ).astype(int)

    courier_load_low, courier_load_high = synthetic_config["courier_load_range"]
    df["courier_load"] = rng.uniform(courier_load_low, courier_load_high, size=n_rows)

    df["is_high_complexity_order"] = (
        (df["order_size"] >= 4)
        | df["seller_category"].isin(["fashion", "electronics"])
    ).astype(int)

    prep_config = synthetic_config["prep_time_by_seller_category"]
    category_mean_map = {
        category: params["mean"] for category, params in prep_config.items()
    }
    df["seller_avg_prep_minutes"] = df["seller_category"].map(category_mean_map)

    return df


def generate_prep_time_minutes(
    df: pd.DataFrame, config: dict[str, Any], rng: np.random.Generator
) -> pd.Series:
    """Generate synthetic seller preparation times with structured effects."""
    synthetic_config = config["synthetic"]
    prep_config = synthetic_config["prep_time_by_seller_category"]

    base_means = df["seller_category"].map(
        {category: params["mean"] for category, params in prep_config.items()}
    ).astype(float)
    base_stds = df["seller_category"].map(
        {category: params["std"] for category, params in prep_config.items()}
    ).astype(float)

    base_draw = rng.normal(loc=base_means.to_numpy(), scale=base_stds.to_numpy())
    order_size_effect = (df["order_size"].to_numpy() - 1.0) * 4.0
    reliability_effect = (1.0 - df["seller_reliability"].to_numpy()) * 50.0
    peak_effect = df["is_peak_hour"].to_numpy() * 8.0
    priority_effect = df["priority_flag"].to_numpy() * -5.0
    complexity_effect = df["is_high_complexity_order"].to_numpy() * 6.0

    prep_time = (
        base_draw
        + order_size_effect
        + reliability_effect
        + peak_effect
        + priority_effect
        + complexity_effect
    )

    prep_min, prep_max = synthetic_config["prep_time_clip"]
    return pd.Series(np.clip(prep_time, prep_min, prep_max), index=df.index)


def generate_pickup_delay_minutes(
    df: pd.DataFrame, config: dict[str, Any], rng: np.random.Generator
) -> pd.Series:
    """Generate synthetic pickup delays driven by workload and coordination factors."""
    synthetic_config = config["synthetic"]
    pickup_config = synthetic_config["pickup_delay"]

    base_mean = pickup_config["base_mean"]
    base_std = pickup_config["base_std"]

    mean_delay = (
        base_mean
        + df["courier_load"].to_numpy() * 18.0
        + df["is_peak_hour"].to_numpy() * 5.0
        + (1.0 - df["seller_reliability"].to_numpy()) * 12.0
    )
    pickup_delay = rng.normal(loc=mean_delay, scale=base_std)

    delay_min, delay_max = synthetic_config["pickup_delay_clip"]
    return pd.Series(np.clip(pickup_delay, delay_min, delay_max), index=df.index)


def apply_peak_hour_congestion(
    df: pd.DataFrame, config: dict[str, Any], rng: np.random.Generator
) -> pd.DataFrame:
    """Modestly increase transport duration during peak hours."""
    df = df.copy()
    low, high = config["synthetic"]["congestion_factor_range"]
    congestion_factor = np.ones(len(df))

    peak_mask = df["is_peak_hour"].to_numpy().astype(bool)
    congestion_factor[peak_mask] = rng.uniform(low, high, size=int(peak_mask.sum()))
    df["delivery_duration_minutes"] = (
        df["delivery_duration_minutes"].to_numpy() * congestion_factor
    )
    return df


def finalize_target(
    df: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, int]:
    """Compute total lead time and filter out implausible target values."""
    df = df.copy()
    df["lead_time_minutes"] = (
        df["prep_time_minutes"]
        + df["pickup_delay_minutes"]
        + df["delivery_duration_minutes"]
    )

    target_config = config["target"]
    target_mask = df["lead_time_minutes"].between(
        target_config["min_lead_time_minutes"],
        target_config["max_lead_time_minutes"],
    )
    rows_dropped_target_filter = int((~target_mask).sum())
    df = df.loc[target_mask].copy()
    return df, rows_dropped_target_filter


def select_final_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the final training-ready columns in a clear, modeling-friendly order."""
    final_columns = [
        "pickup_datetime",
        "lead_time_minutes",
        "prep_time_minutes",
        "pickup_delay_minutes",
        "delivery_duration_minutes",
        "seller_category",
        "seller_reliability",
        "seller_avg_prep_minutes",
        "order_size",
        "priority_flag",
        "courier_load",
        "is_high_complexity_order",
        "hour_of_day",
        "day_of_week",
        "month",
        "is_weekend",
        "is_peak_hour",
        "trip_distance_km",
        "pickup_latitude",
        "pickup_longitude",
        "dropoff_latitude",
        "dropoff_longitude",
    ]
    return df.loc[:, final_columns].copy()


def assign_splits(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    """Assign train, validation, and test splits using time-aware or random logic."""
    df = df.copy()
    split_config = config["split"]
    n_rows = len(df)
    train_end = int(n_rows * split_config["train_frac"])
    val_end = train_end + int(n_rows * split_config["val_frac"])

    if split_config["time_aware"]:
        split_strategy = "time_aware"
        df = df.sort_values("pickup_datetime").reset_index(drop=True)
    else:
        split_strategy = "random_seeded"
        df = (
            df.sample(frac=1.0, random_state=config["random_seed"])
            .reset_index(drop=True)
        )

    split = np.full(n_rows, "test", dtype=object)
    split[:train_end] = "train"
    split[train_end:val_end] = "val"
    df["split"] = split
    return df, split_strategy


def dataset_statistics(series: pd.Series) -> dict[str, float]:
    """Compute JSON-serializable summary statistics for a numeric series."""
    return {
        "mean": round(float(series.mean()), 4),
        "std": round(float(series.std(ddof=0)), 4),
        "min": round(float(series.min()), 4),
        "median": round(float(series.median()), 4),
        "max": round(float(series.max()), 4),
    }


def build_summary(
    df: pd.DataFrame, stats: dict[str, Any], split_strategy: str
) -> dict[str, Any]:
    """Create a structured dataset summary for downstream inspection."""
    split_sizes = {key: int(value) for key, value in df["split"].value_counts().items()}
    seller_distribution = {
        key: int(value) for key, value in df["seller_category"].value_counts().items()
    }

    summary = {
        **stats,
        "final_dataset_size": int(len(df)),
        "split_sizes": split_sizes,
        "column_list": list(df.columns),
        "target_statistics": dataset_statistics(df["lead_time_minutes"]),
        "component_statistics": {
            "prep_time_minutes": dataset_statistics(df["prep_time_minutes"]),
            "pickup_delay_minutes": dataset_statistics(df["pickup_delay_minutes"]),
            "delivery_duration_minutes": dataset_statistics(
                df["delivery_duration_minutes"]
            ),
        },
        "seller_category_distribution": seller_distribution,
        "split_strategy": split_strategy,
    }
    return summary


def save_artifacts(
    df: pd.DataFrame, summary: dict[str, Any], processed_output_dir: Path
) -> None:
    """Persist the full dataset, splits, and summary metadata."""
    processed_output_dir.mkdir(parents=True, exist_ok=True)

    full_dataset_path = processed_output_dir / "full_dataset.csv"
    train_path = processed_output_dir / "train.csv"
    val_path = processed_output_dir / "val.csv"
    test_path = processed_output_dir / "test.csv"
    summary_path = processed_output_dir / "dataset_summary.json"

    df.to_csv(full_dataset_path, index=False)
    df.loc[df["split"] == "train"].to_csv(train_path, index=False)
    df.loc[df["split"] == "val"].to_csv(val_path, index=False)
    df.loc[df["split"] == "test"].to_csv(test_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    """Run the proxy dataset construction pipeline."""
    print("Running dataset construction pipeline.")
    config = load_config("config/dataset_config.yaml")
    validate_config(config)

    random_seed = config["random_seed"]
    rng = np.random.default_rng(random_seed)
    processed_output_dir = Path(config["processed_output_dir"])

    print("Loading raw taxi dataset.")
    raw_df = load_raw_dataset(Path(config["raw_trip_dataset_path"]))
    stats: dict[str, Any] = {"total_rows_loaded": int(len(raw_df))}

    print("Dropping rows with missing transport values.")
    df, rows_dropped_missing = drop_missing_transport_rows(raw_df)
    stats["rows_dropped_missing_required_values"] = int(rows_dropped_missing)

    print("Applying transport validity filters.")
    df, transport_filter_stats = filter_transport_rows(df, config)
    stats.update(transport_filter_stats)

    print("Computing trip-distance and transport-duration features.")
    df, rows_dropped_distance = compute_transport_features(df, config)
    stats["rows_dropped_distance_filter"] = int(rows_dropped_distance)

    print("Applying deterministic subsampling if needed.")
    df = deterministic_subsample(df, config["sample_size"], random_seed)

    print("Constructing temporal features.")
    df = add_temporal_features(df)

    print("Generating synthetic marketplace variables.")
    df = generate_synthetic_features(df, config, rng)
    df["prep_time_minutes"] = generate_prep_time_minutes(df, config, rng)
    df["pickup_delay_minutes"] = generate_pickup_delay_minutes(df, config, rng)
    df = apply_peak_hour_congestion(df, config, rng)

    print("Computing final lead-time target.")
    df, rows_dropped_target = finalize_target(df, config)
    stats["rows_dropped_target_filter"] = int(rows_dropped_target)

    if df.empty:
        raise ValueError("No rows remain after dataset construction filters.")

    df = select_final_columns(df)
    df, split_strategy = assign_splits(df, config)

    print("Saving processed datasets and summary artifacts.")
    summary = build_summary(df, stats, split_strategy)
    save_artifacts(df, summary, processed_output_dir)

    print("Dataset construction complete.")
    print(f"Final dataset size: {len(df)} rows")
    print(f"Artifacts written to: {processed_output_dir}")


if __name__ == "__main__":
    main()
