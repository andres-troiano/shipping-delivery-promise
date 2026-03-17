# Technical Spec — Quantile Estimation for Delivery Promise Intervals

## Objective

Implement the quantile modeling stage for the Mercado Libre Delivery Promise Optimization prototype.

This stage trains models that estimate conditional quantiles of:

```
lead_time_minutes
```

using the processed dataset produced earlier.

The goal is to move from:

* point prediction

to:

* distribution-aware prediction
* delivery promise interval construction
* uncertainty-aware evaluation

This stage focuses on:

* training quantile regression models
* generating lower and upper bounds for lead time
* evaluating interval quality
* saving reusable artifacts for later policy analysis

Important:
This stage does not implement promise policy comparison. That belongs to the next stage.

# Deliverables

Implement:

```
src/train_quantiles.py
```

Update:

```
config/model_config.yaml
```

The script consumes:

```
data/processed/train.csv
data/processed/val.csv
data/processed/test.csv
```

Artifacts should be written under:

```
artifacts/quantile_model/

    q50_model.pkl
    q90_model.pkl
    metrics.json

    interval_predictions_val.csv
    interval_predictions_test.csv

    feature_importance_q50.csv
    feature_importance_q90.csv
```

Create the directory if it does not exist.

# Dataset Schema

The processed dataset includes columns such as:

```
pickup_datetime
lead_time_minutes
prep_time_minutes
pickup_delay_minutes
delivery_duration_minutes
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
split
```

The modeling target is:

```
lead_time_minutes
```

This value is constructed as:

```
lead_time_minutes =
    prep_time_minutes
  + pickup_delay_minutes
  + delivery_duration_minutes
```

Because these components directly compose the target, they must not be used as model features.

# Feature Handling Strategy

The project intentionally avoids explicitly listing numeric features in configuration in order to prevent configuration drift if new features are added in the dataset construction stage.

Feature resolution follows this rule:

```
numeric_features =
    all_columns
    - categorical_features
    - exclude_columns
```

The configuration therefore only defines:

* categorical features
* columns to exclude

Example from `model_config.yaml`:

```yaml
features:
  categorical:
    - seller_category

  exclude_columns:
    - lead_time_minutes
    - prep_time_minutes
    - pickup_delay_minutes
    - delivery_duration_minutes
    - pickup_datetime
    - split
```

### Leakage columns

These must always be excluded:

```
lead_time_minutes
prep_time_minutes
pickup_delay_minutes
delivery_duration_minutes
```

### Metadata columns

Also excluded:

```
pickup_datetime
split
```

The remaining columns become numeric features automatically.

# Quantile Modeling Goal

Train models that estimate:

```
Q_0.50(lead_time_minutes | X)
Q_0.90(lead_time_minutes | X)
```

These quantiles form a delivery promise interval:

```
[q50, q90]
```

Interpretation:

* `q50` → central estimate
* `q90` → operational deadline

This reflects uncertainty in delivery time.

# Quantile Set

Minimum required quantiles:

```
0.50
0.90
```

The configuration may allow additional quantiles later, but the implementation target for this stage remains:

* q50
* q90

# Model Choice

Use:

```
LightGBMRegressor
```

with the quantile objective.

For each quantile `q`, train a separate model:

```
objective = "quantile"
alpha = q
```

This is appropriate for:

* tabular data
* fast training
* interpretable feature importance

Avoid introducing:

* neural quantile models
* conformal prediction
* Bayesian methods

# Preprocessing Pipeline

Use the same preprocessing structure as in the point prediction modeling stage.

Recommended pattern:

Numeric features:

```
SimpleImputer(strategy="median")
```

Categorical features:

```
SimpleImputer(strategy="most_frequent")
OneHotEncoder(handle_unknown="ignore")
```

Combine using a ColumnTransformer inside a scikit-learn Pipeline.

# Pipeline Steps

## 1. Load configuration

Read:

```
config/model_config.yaml
```

Validate:

* dataset paths exist
* target column exists
* quantiles are valid
* artifact directory can be created

## 2. Load processed datasets

Load:

```
train.csv
val.csv
test.csv
```

Verify:

* datasets are not empty
* target column exists
* schemas are consistent

## 3. Resolve feature columns

Using the config:

```
numeric_features =
    all_columns
    - categorical_features
    - exclude_columns
```

Perform sanity checks:

* ensure at least one numeric feature
* ensure categorical features exist

Log the resolved feature sets.

## 4. Build preprocessing pipeline

Construct a reusable preprocessing pipeline.

Then create a model pipeline for each quantile.

## 5. Train quantile models

Train one model per quantile.

Required models:

```
q50
q90
```

Training split:

```
train
```

Evaluation splits:

```
validation
test
```

## 6. Generate quantile predictions

Generate predictions for:

```
validation
test
```

Create columns:

```
actual_lead_time_minutes
pred_q50
pred_q90
split
```

Derived interval columns:

```
interval_lower = pred_q50
interval_upper = pred_q90
interval_width = interval_upper - interval_lower

is_late_vs_upper = actual > interval_upper
is_within_interval = interval_lower <= actual <= interval_upper
```

# Quantile Monotonicity

Independent quantile models can produce crossing predictions.

If configured:

```
enforce_monotonic_quantiles = true
```

Apply correction:

```
pred_q90 = max(pred_q90, pred_q50)
```

Track how many rows required correction.

# Evaluation Metrics

Compute metrics on validation and test.

### Interval Coverage

```
mean(interval_lower <= actual <= interval_upper)
```

For `[q50, q90]`, nominal coverage:

```
0.90 - 0.50 = 0.40
```

### Average Interval Width

```
mean(interval_upper - interval_lower)
```

Represents delivery promise precision.

### Late Delivery Rate vs Upper Bound

```
mean(actual > pred_q90)
```

Expected value:

```
≈ 0.10
```

### Pinball Loss

Compute pinball loss for:

```
q50
q90
```

### Quantile Calibration

Also compute:

```
mean(actual <= pred_q50)
mean(actual <= pred_q90)
```

Expected values:

```
≈ 0.50
≈ 0.90
```

# Metrics Output

Save metrics:

```
artifacts/quantile_model/metrics.json
```

Example structure:

```json
{
  "validation": {
    "coverage_q50_q90": ...,
    "avg_interval_width_q50_q90": ...,
    "late_rate_vs_q90": ...,
    "pinball_loss_q50": ...,
    "pinball_loss_q90": ...
  },
  "test": {
    "coverage_q50_q90": ...,
    "avg_interval_width_q50_q90": ...,
    "late_rate_vs_q90": ...,
    "pinball_loss_q50": ...,
    "pinball_loss_q90": ...
  }
}
```

# Feature Importance

Extract feature importance from each quantile model.

Save:

```
feature_importance_q50.csv
feature_importance_q90.csv
```

Columns:

```
feature_name
importance
```

# Artifact Saving

Save:

```
q50_model.pkl
q90_model.pkl
metrics.json
interval_predictions_val.csv
interval_predictions_test.csv
feature_importance_q50.csv
feature_importance_q90.csv
```

Use:

```
joblib.dump(...)
```

# Logging Summary

At the end of the script print:

```
train / val / test sizes
resolved numeric features
resolved categorical features
trained quantiles
validation coverage
validation interval width
validation late rate
test coverage
test interval width
test late rate
quantile crossing corrections
artifact output path
```

# Acceptance Criteria

This stage is complete when:

* quantile models for `q50` and `q90` are trained
* leakage columns are excluded
* interval predictions are generated
* interval metrics are computed
* artifacts are saved
* results are reproducible with the configured seed

# Scope Reminder

This stage estimates uncertainty.

It does not yet decide which delivery promise policy is optimal.

Policy comparison and trade-off analysis belong to the next stage.
