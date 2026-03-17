# Technical Spec — Proxy Dataset Construction

## Objective

Implement the proxy dataset construction pipeline for the Mercado Libre Delivery Promise Optimization prototype.

Because the challenge does not provide operational logistics data, this stage builds a training-ready dataset by combining:

1. real urban transport durations from the Kaggle NYC Taxi Trip Duration dataset
2. synthetic seller-side operational variables representing marketplace fulfillment dynamics

The resulting dataset should simulate the full delivery lead time:

```
lead_time_minutes =
prep_time_minutes
+ pickup_delay_minutes
+ delivery_duration_minutes
```

Where:

* `delivery_duration_minutes` comes from real taxi trip durations
* `prep_time_minutes` is synthetically generated
* `pickup_delay_minutes` is synthetically generated

The goal of the synthetic augmentation is not to perfectly simulate real logistics operations, but to introduce structured uncertainty that enables meaningful:

* delivery time prediction
* uncertainty modeling
* delivery promise policy evaluation

No models should be trained in this stage.

## Deliverables

Implement:

```
src/build_dataset.py
```

Configuration file:

```
config/dataset_config.yaml
```

Outputs should be saved under:

```
data/
  raw/
      nyc_taxi_train.csv
  processed/
      full_dataset.csv
      train.csv
      val.csv
      test.csv
      dataset_summary.json
```

If directories do not exist, the script should create them.

## Dataset Source

This project uses the Kaggle NYC Taxi Trip Duration dataset as a proxy for urban transport time.

Raw dataset:

```
data/raw/nyc_taxi_train.csv
```

This corresponds to Kaggle’s `train.csv`.

The Kaggle `test.csv` file should not be used, because it does not contain `trip_duration`.

## Expected Raw Schema

The raw dataset contains:

```
id
vendor_id
pickup_datetime
dropoff_datetime
passenger_count
pickup_longitude
pickup_latitude
dropoff_longitude
dropoff_latitude
store_and_fwd_flag
trip_duration
```

Only a subset of these fields is required.

Key fields used in this project:

```
pickup_datetime
dropoff_datetime
trip_duration
pickup_latitude
pickup_longitude
dropoff_latitude
dropoff_longitude
```

## Configuration File

Example structure:

```yaml
raw_trip_dataset_path: data/raw/nyc_taxi_train.csv
processed_output_dir: data/processed

random_seed: 42
sample_size: 100000

transport_filter:
  min_duration_seconds: 180
  max_duration_seconds: 7200

geo_filter:
  min_lat: 40.5
  max_lat: 41.0
  min_lon: -74.2
  max_lon: -73.6

distance_filter:
  min_trip_distance_km: 0.1

target:
  min_lead_time_minutes: 15
  max_lead_time_minutes: 1440

synthetic:
  seller_category_probs:
    restaurant: 0.25
    pharmacy: 0.15
    supermarket: 0.20
    fashion: 0.20
    electronics: 0.20

  prep_time_by_seller_category:
    restaurant: {mean: 20, std: 8}
    pharmacy: {mean: 12, std: 5}
    supermarket: {mean: 30, std: 10}
    fashion: {mean: 90, std: 30}
    electronics: {mean: 120, std: 40}

  pickup_delay:
    base_mean: 10
    base_std: 5

  seller_reliability_range: [0.7, 0.99]
  courier_load_range: [0.0, 1.0]

  order_size_range: [1, 5]
  priority_probability: 0.15

  prep_time_clip: [3, 240]
  pickup_delay_clip: [0, 120]

split:
  train_frac: 0.7
  val_frac: 0.15
  test_frac: 0.15
  time_aware: true
```

## Implementation Requirements

`src/build_dataset.py` must include:

* module docstring
* `main()` entry point
* helper functions
* configuration loading
* deterministic random seed
* logging or printed progress

The script should be runnable from the command line.

## Pipeline Steps

### 1. Load configuration

Read:

```
config/dataset_config.yaml
```

Validate:

* raw dataset exists
* split fractions sum to 1
* sample size > 0
* seller category probabilities sum to 1

Fail early with clear errors if invalid.

### 2. Load raw taxi dataset

Load:

```
data/raw/nyc_taxi_train.csv
```

into a pandas DataFrame.

Convert:

```
pickup_datetime
dropoff_datetime
```

to pandas datetime.

Drop rows with missing values in required transport columns.

At minimum, rows missing any of the following should be removed:

```
pickup_datetime
dropoff_datetime
trip_duration
pickup_latitude
pickup_longitude
dropoff_latitude
dropoff_longitude
```

### 3. Filter invalid transport rows

Apply duration filter in seconds:

```
180 ≤ trip_duration ≤ 7200
```

Apply geographic filters:

```
40.5 ≤ latitude ≤ 41.0
-74.2 ≤ longitude ≤ -73.6
```

Check both pickup and dropoff coordinates.

Drop rows violating these constraints.

### 4. Compute transport features

Convert transport duration from seconds to minutes:

```
delivery_duration_minutes = trip_duration / 60
```

Compute trip distance using a haversine formula:

```
trip_distance_km = haversine(pickup, dropoff)
```

Filter zero or near-zero trips:

```
trip_distance_km ≥ 0.1
```

This avoids degenerate trips where pickup and dropoff are effectively the same.

### 5. Optional subsampling

If the cleaned dataset size exceeds `sample_size`, randomly sample rows using the configured seed.

Sampling must be deterministic.

### 6. Construct temporal features

Derive from `pickup_datetime`:

```
hour_of_day
day_of_week
month
is_weekend
```

Define:

```
is_peak_hour
```

Example peak-hour definition:

```
11–14
18–21
```

This can be implemented as an explicit rule in Python.

### 7. Generate synthetic marketplace variables

Create synthetic variables representing seller, order, and operational uncertainty.

#### Seller features

```
seller_category
seller_reliability
seller_avg_prep_minutes
```

#### Order features

```
order_size
priority_flag
```

#### Operational features

```
courier_load
```

#### Derived flags

```
is_high_complexity_order
```

Suggested generation rules:

* `seller_category` sampled from a categorical distribution using configured probabilities
* `seller_reliability` sampled from a continuous uniform distribution
* `order_size` sampled as a small integer in a configured range
* `priority_flag` sampled as a Bernoulli variable
* `courier_load` sampled from a continuous uniform distribution

Synthetic variables should create plausible structure, not arbitrary noise.

### 8. Generate `prep_time_minutes`

Generate `prep_time_minutes` as the first synthetic component of lead time.

Base distribution is determined by:

```
seller_category
```

Then adjust based on:

* `order_size`
* `seller_reliability`
* `is_peak_hour`
* optionally `priority_flag`

The logic should reflect plausible patterns such as:

* restaurants and pharmacies generally faster than fashion or electronics
* lower seller reliability increasing prep time
* larger orders increasing prep time
* peak periods adding operational friction

Clip values to configured bounds.

### 9. Generate `pickup_delay_minutes`

Generate `pickup_delay_minutes` separately from prep time.

This delay should depend on:

* `courier_load`
* `is_peak_hour`
* `seller_reliability`

The synthetic logic should reflect patterns such as:

* higher courier load increasing pickup delay
* peak periods increasing pickup delay
* lower seller reliability slightly worsening pickup coordination

Use stochastic sampling and clip to configured bounds.

### 10. Optional congestion adjustment

Optionally increase delivery duration slightly during peak hours.

Example:

```
delivery_duration_minutes *= congestion_factor
```

Where the congestion factor is modest, for example in the range:

```
1.05–1.15
```

This helps make peak-hour effects influence the full lead-time structure, not only the synthetic components.

### 11. Construct final target

Compute:

```
lead_time_minutes =
prep_time_minutes
+ pickup_delay_minutes
+ delivery_duration_minutes
```

Keep the three components explicitly:

```
prep_time_minutes
pickup_delay_minutes
delivery_duration_minutes
```

Filter rows outside configured target bounds.

### 12. Define final dataset columns

The processed dataset should contain at least:

#### Target

```
lead_time_minutes
```

#### Interpretable components

```
prep_time_minutes
pickup_delay_minutes
delivery_duration_minutes
```

#### Candidate model features

```
seller_category
seller_reliability
seller_avg_prep_minutes
order_size
priority_flag
courier_load
is_high_complexity_order
hour_of_day
day_of_week
month
is_weekend
is_peak_hour
trip_distance_km
pickup_latitude
pickup_longitude
dropoff_latitude
dropoff_longitude
```

Do not perform feature encoding in this stage.

That belongs to later modeling stages.

### 13. Dataset splitting

Create:

```
train
val
test
```

If timestamps exist and `time_aware = true`, perform a time-based split using `pickup_datetime`:

```
earliest → train
middle → val
latest → test
```

Otherwise perform seeded random split.

The split strategy used must be recorded in the summary file.

### 14. Save artifacts

Save:

```
full_dataset.csv
train.csv
val.csv
test.csv
```

Include a:

```
split
```

column in `full_dataset.csv`.

### 15. Save dataset summary

Create:

```
dataset_summary.json
```

Include at least:

* total rows loaded
* rows dropped due to missing required values
* rows dropped by duration filter
* rows dropped by geographic filter
* rows dropped by distance filter
* final dataset size
* split sizes
* column list
* target statistics
* component statistics
* seller category distribution
* split strategy

## Reproducibility

All randomness must use the configured `random_seed`.

Running the pipeline twice with the same inputs should produce identical outputs.

## Coding Guidelines

Use:

* pandas
* numpy
* pyyaml
* pathlib

Avoid:

* heavy frameworks
* unnecessary OOP
* premature optimization

This should remain a clear, lightweight technical-challenge prototype.

## Acceptance Criteria

This stage is complete when:

* `build_dataset.py` is implemented
* raw taxi data loads successfully
* invalid transport rows are filtered
* transport duration is converted into `delivery_duration_minutes`
* `trip_distance_km` is computed
* synthetic seller-side variables are generated
* `lead_time_minutes` is computed
* dataset splits are created
* output artifacts are saved
* results are deterministic
* dataset is coherent and ready for modeling
