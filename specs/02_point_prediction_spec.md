# Technical Spec — Lead Time Point Prediction Model

## Objective

Implement the baseline point prediction model for the delivery lead time.

This stage trains a regression model to predict:

```
lead_time_minutes
```

using the proxy dataset generated previously.

The goal of this stage is to:

* validate that the constructed dataset contains learnable signal
* establish a baseline predictive model
* quantify predictive performance
* identify important drivers of delivery lead time
* produce artifacts used by later stages (quantile prediction and policy evaluation)

This stage focuses on:

* loading processed datasets
* feature preprocessing
* baseline comparison
* model training
* validation and test evaluation
* artifact generation

This stage does not implement interval prediction or decision policies.

# Deliverables

Implement:

```
src/train_model.py
```

Update:

```
config/model_config.yaml
```

The script should consume the processed datasets produced earlier:

```
data/processed/train.csv
data/processed/val.csv
data/processed/test.csv
```

and produce model artifacts:

```
artifacts/
  point_model/
      model.pkl
      metrics.json
      feature_importance.csv
      predictions_val.csv
      predictions_test.csv
      model_config_snapshot.yaml
```

The artifacts directory should be created automatically if it does not exist.

# Modeling Goal

Train a regression model estimating:

```
E[lead_time_minutes | X]
```

This model is not the final system objective, but a baseline predictor.

It serves several purposes:

* verifies that the proxy dataset contains meaningful signal
* provides a benchmark against which interval models can be compared
* identifies important drivers of lead time
* produces predictions used in diagnostic analysis

Later stages will extend this to quantile models for interval prediction.

# Model Choice

Use:

```
LightGBMRegressor
```

Reasoning:

* strong performance on tabular datasets
* handles nonlinear relationships
* efficient training
* widely used baseline for structured ML problems

No model comparison or hyperparameter tuning is required in this stage.

# Configuration File

Update `config/model_config.yaml`.

Example structure:

```yaml
target_column: lead_time_minutes

data:
  train_path: data/processed/train.csv
  val_path: data/processed/val.csv
  test_path: data/processed/test.csv

artifacts:
  point_model_dir: artifacts/point_model

features:

  categorical:
    - seller_category
    - pickup_zone
    - dropoff_zone

  exclude_columns:
    - lead_time_minutes
    - prep_time_minutes
    - pickup_delay_minutes
    - delivery_duration_minutes

training:
  random_seed: 42

lightgbm_params:
  objective: regression
  n_estimators: 300
  learning_rate: 0.05
  num_leaves: 31
  min_child_samples: 20
  subsample: 0.8
  colsample_bytree: 0.8

evaluation:
  clip_min_prediction: 1.0
```

# Feature Selection Strategy

The dataset produced earlier contains many columns, including the additive components of the target.

Because:

```
lead_time_minutes =
prep_time_minutes
+ pickup_delay_minutes
+ delivery_duration_minutes
```

the model must not train on these component variables, as that would create severe target leakage.

Therefore:

```
exclude_columns
```

defines variables removed from the feature set.

All remaining columns are considered candidate features.

Numeric features are inferred automatically.

Categorical features are specified explicitly.

# Implementation Requirements for `src/train_model.py`

The script should be fully implemented and runnable from the command line.

It must include:

* module docstring
* `main()` entry point
* YAML configuration loading
* dataset validation
* preprocessing pipeline
* baseline evaluation
* model training
* artifact saving

# Pipeline Overview

The script should follow this workflow.

# 1. Load configuration

Read:

```
config/model_config.yaml
```

Validate:

* dataset paths exist
* artifact directory can be created
* target column exists in datasets
* listed categorical columns exist

Fail with clear errors if configuration is invalid.

# 2. Load processed datasets

Load:

```
train.csv
val.csv
test.csv
```

into pandas DataFrames.

Validate:

* datasets are non-empty
* schemas are consistent
* target column exists

# 3. Resolve feature columns

Determine model input columns.

Steps:

1. Remove columns listed in `exclude_columns`
2. Remove the target column
3. Separate categorical and numeric features

Numeric features are inferred automatically as remaining non-categorical columns.

Fail if no usable features remain.

# 4. Baseline model

Compute a naive baseline predictor using the mean lead time from the training set.

Prediction rule:

```
ŷ = mean(train_target)
```

Evaluate baseline performance on:

* validation set
* test set

Metrics:

* MAE
* RMSE

This baseline serves as a sanity check that the dataset contains predictive signal.

# 5. Build preprocessing pipeline

Construct a scikit-learn preprocessing pipeline.

Numeric features:

```
SimpleImputer(strategy="median")
```

Categorical features:

```
SimpleImputer(strategy="most_frequent")
OneHotEncoder(handle_unknown="ignore")
```

Combine with:

```
ColumnTransformer
```

# 6. Build model pipeline

Attach the model to the preprocessing pipeline.

Structure:

```
Pipeline(
    preprocessing
    LightGBMRegressor
)
```

Use parameters defined in `lightgbm_params`.

Set the random seed for reproducibility.

# 7. Train the model

Train the pipeline on the training split only.

Do not use validation or test data during fitting.

# 8. Generate predictions

Generate predictions for:

```
validation split
test split
```

Apply minimum clipping:

```
prediction = max(prediction, clip_min_prediction)
```

to avoid negative lead time predictions.

# 9. Compute evaluation metrics

Compute metrics for:

* baseline model
* LightGBM model

Metrics:

```
MAE
RMSE
R²
```

Store results in:

```
metrics.json
```

Example structure:

```
{
  "baseline": {
    "validation": {...},
    "test": {...}
  },
  "lightgbm": {
    "validation": {...},
    "test": {...}
  }
}
```

# 10. Save prediction outputs

Save row-level predictions:

```
predictions_val.csv
predictions_test.csv
```

Include columns:

```
actual_lead_time_minutes
predicted_lead_time_minutes
abs_error
split
```

Optionally include a few diagnostic features:

```
seller_category
hour_of_day
is_peak_hour
```

# 11. Extract feature importance

Extract feature importance from the trained LightGBM model.

Prefer:

```
importance_type = "gain"
```

Save:

```
feature_importance.csv
```

with columns:

```
feature_name
importance
```

# 12. Save artifacts

Save the following files:

```
model.pkl
metrics.json
feature_importance.csv
predictions_val.csv
predictions_test.csv
model_config_snapshot.yaml
```

Serialize the model using:

```
joblib.dump()
```

# 13. Log training summary

Print a concise summary:

```
train rows
validation rows
test rows
number of features
baseline MAE
model MAE
artifact location
```

# Reproducibility Requirements

Use the configured random seed.

Ensure deterministic behavior where possible by setting seeds for:

* numpy
* LightGBM

# Error Handling

Handle common failure cases clearly:

* missing datasets
* missing target column
* missing categorical columns
* empty datasets
* failure to create artifact directory

Errors should be explicit and readable.

# Coding Style

Use:

* pandas
* scikit-learn
* lightgbm
* yaml
* joblib
* pathlib
* json

Avoid:

* unnecessary abstractions
* custom estimator classes
* experiment tracking frameworks
* hyperparameter tuning

This repository represents a technical challenge prototype, not a full ML platform.

# Acceptance Criteria

This stage is complete when:

* `src/train_model.py` is fully implemented
* the script loads the processed datasets
* the script excludes target component variables
* the script trains a LightGBM regression model
* the script computes baseline and model metrics
* MAE and RMSE are reported
* model artifacts are saved
* feature importance is exported
* predictions are saved for validation and test splits
* training is reproducible using the configured seed
