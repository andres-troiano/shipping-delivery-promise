from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.build_dataset import (
    add_temporal_features,
    assign_splits,
    compute_transport_features,
    drop_missing_transport_rows,
    filter_transport_rows,
    finalize_target,
    generate_pickup_delay_minutes,
    generate_prep_time_minutes,
    generate_synthetic_features,
)


@pytest.fixture
def test_config() -> dict:
    return {
        "random_seed": 42,
        "transport_filter": {
            "min_duration_seconds": 180,
            "max_duration_seconds": 7200,
        },
        "geo_filter": {
            "min_lat": 40.5,
            "max_lat": 41.0,
            "min_lon": -74.2,
            "max_lon": -73.6,
        },
        "distance_filter": {
            "min_trip_distance_km": 0.1,
        },
        "target": {
            "min_lead_time_minutes": 15,
            "max_lead_time_minutes": 1440,
        },
        "synthetic": {
            "seller_category_probs": {
                "restaurant": 0.25,
                "pharmacy": 0.15,
                "supermarket": 0.20,
                "fashion": 0.20,
                "electronics": 0.20,
            },
            "prep_time_by_seller_category": {
                "restaurant": {"mean": 20, "std": 8},
                "pharmacy": {"mean": 12, "std": 5},
                "supermarket": {"mean": 30, "std": 10},
                "fashion": {"mean": 90, "std": 30},
                "electronics": {"mean": 120, "std": 40},
            },
            "pickup_delay": {
                "base_mean": 10,
                "base_std": 5,
            },
            "seller_reliability_range": [0.7, 0.99],
            "courier_load_range": [0.0, 1.0],
            "order_size_range": [1, 5],
            "priority_probability": 0.15,
            "prep_time_clip": [3, 240],
            "pickup_delay_clip": [0, 120],
            "congestion_factor_range": [1.05, 1.15],
        },
        "split": {
            "train_frac": 0.5,
            "val_frac": 0.25,
            "test_frac": 0.25,
            "time_aware": True,
        },
    }


def test_invalid_row_filtering_removes_expected_rows(test_config: dict) -> None:
    df = pd.DataFrame(
        [
            # valid row
            {
                "pickup_datetime": pd.Timestamp("2016-03-14 12:00:00"),
                "dropoff_datetime": pd.Timestamp("2016-03-14 12:10:00"),
                "trip_duration": 600,
                "pickup_latitude": 40.75,
                "pickup_longitude": -73.99,
                "dropoff_latitude": 40.76,
                "dropoff_longitude": -73.98,
            },
            # missing required field
            {
                "pickup_datetime": pd.NaT,
                "dropoff_datetime": pd.Timestamp("2016-03-14 12:15:00"),
                "trip_duration": 700,
                "pickup_latitude": 40.75,
                "pickup_longitude": -73.99,
                "dropoff_latitude": 40.77,
                "dropoff_longitude": -73.97,
            },
            # invalid duration
            {
                "pickup_datetime": pd.Timestamp("2016-03-14 12:20:00"),
                "dropoff_datetime": pd.Timestamp("2016-03-14 12:22:00"),
                "trip_duration": 120,
                "pickup_latitude": 40.75,
                "pickup_longitude": -73.99,
                "dropoff_latitude": 40.77,
                "dropoff_longitude": -73.97,
            },
            # invalid geography
            {
                "pickup_datetime": pd.Timestamp("2016-03-14 12:30:00"),
                "dropoff_datetime": pd.Timestamp("2016-03-14 12:40:00"),
                "trip_duration": 600,
                "pickup_latitude": 41.2,
                "pickup_longitude": -73.99,
                "dropoff_latitude": 40.77,
                "dropoff_longitude": -73.97,
            },
            # zero-distance / near-zero trip
            {
                "pickup_datetime": pd.Timestamp("2016-03-14 12:45:00"),
                "dropoff_datetime": pd.Timestamp("2016-03-14 12:55:00"),
                "trip_duration": 600,
                "pickup_latitude": 40.75,
                "pickup_longitude": -73.99,
                "dropoff_latitude": 40.75,
                "dropoff_longitude": -73.99,
            },
        ]
    )

    df, dropped_missing = drop_missing_transport_rows(df)
    assert dropped_missing == 1
    assert len(df) == 4

    df, filter_stats = filter_transport_rows(df, test_config)
    assert filter_stats["rows_dropped_duration_filter"] == 1
    assert filter_stats["rows_dropped_geo_filter"] == 1
    assert len(df) == 2

    df, dropped_distance = compute_transport_features(df, test_config)
    assert dropped_distance == 1
    assert len(df) == 1

    remaining = df.iloc[0]
    assert remaining["trip_duration"] == 600
    assert remaining["delivery_duration_minutes"] == 10.0
    assert remaining["pickup_latitude"] == 40.75
    assert remaining["pickup_longitude"] == -73.99
    assert remaining["dropoff_latitude"] == 40.76
    assert remaining["dropoff_longitude"] == -73.98
    assert remaining["trip_distance_km"] >= 0.1


def test_target_construction_matches_component_sum(test_config: dict) -> None:
    df = pd.DataFrame(
        {
            "prep_time_minutes": [20.0, 45.5, 12.25],
            "pickup_delay_minutes": [5.0, 10.25, 2.75],
            "delivery_duration_minutes": [15.0, 22.5, 8.5],
        }
    )

    expected = (
        df["prep_time_minutes"]
        + df["pickup_delay_minutes"]
        + df["delivery_duration_minutes"]
    )

    finalized_df, rows_dropped = finalize_target(df.copy(), test_config)

    assert rows_dropped == 0
    assert np.allclose(finalized_df["lead_time_minutes"], expected)


def test_synthetic_generation_is_deterministic_for_same_seed(
    test_config: dict,
) -> None:
    base_df = pd.DataFrame(
        {
            "pickup_datetime": pd.to_datetime(
                [
                    "2016-03-14 12:00:00",
                    "2016-03-14 19:00:00",
                    "2016-03-19 09:30:00",
                ]
            )
        }
    )
    base_df = add_temporal_features(base_df)

    rng_one = np.random.default_rng(42)
    rng_two = np.random.default_rng(42)

    generated_one = generate_synthetic_features(base_df.copy(), test_config, rng_one)
    generated_one["prep_time_minutes"] = generate_prep_time_minutes(
        generated_one, test_config, rng_one
    )
    generated_one["pickup_delay_minutes"] = generate_pickup_delay_minutes(
        generated_one, test_config, rng_one
    )

    generated_two = generate_synthetic_features(base_df.copy(), test_config, rng_two)
    generated_two["prep_time_minutes"] = generate_prep_time_minutes(
        generated_two, test_config, rng_two
    )
    generated_two["pickup_delay_minutes"] = generate_pickup_delay_minutes(
        generated_two, test_config, rng_two
    )

    for column in [
        "seller_category",
        "seller_reliability",
        "order_size",
        "priority_flag",
        "courier_load",
        "prep_time_minutes",
        "pickup_delay_minutes",
    ]:
        pdt.assert_series_equal(generated_one[column], generated_two[column])

    assert generated_one["seller_reliability"].between(0.7, 0.99).all()
    assert generated_one["courier_load"].between(0.0, 1.0).all()
    assert generated_one["prep_time_minutes"].between(3, 240).all()
    assert generated_one["pickup_delay_minutes"].between(0, 120).all()


def test_assign_splits_uses_time_order_when_time_aware(test_config: dict) -> None:
    df = pd.DataFrame(
        {
            "pickup_datetime": pd.to_datetime(
                [
                    "2016-03-14 12:00:00",
                    "2016-03-10 12:00:00",
                    "2016-03-20 12:00:00",
                    "2016-03-15 12:00:00",
                ]
            )
        }
    )

    split_df, split_strategy = assign_splits(df, test_config)

    assert split_strategy == "time_aware"
    assert split_df["pickup_datetime"].is_monotonic_increasing

    expected_dates = pd.Series(
        pd.to_datetime(
            [
                "2016-03-10 12:00:00",
                "2016-03-14 12:00:00",
                "2016-03-15 12:00:00",
                "2016-03-20 12:00:00",
            ]
        ),
        name="pickup_datetime",
    )
    pdt.assert_series_equal(
        split_df["pickup_datetime"].reset_index(drop=True),
        expected_dates,
    )

    assert split_df["split"].tolist() == ["train", "train", "val", "test"]
