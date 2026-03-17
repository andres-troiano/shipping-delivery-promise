# Technical Spec — Policy Trade-off Analysis

## Objective

Implement the policy evaluation stage for the Mercado Libre Delivery Promise Optimization prototype.

This stage evaluates buyer-facing promise policies using the quantile predictions produced in the previous stage.

The goal is to quantify the trade-off between:

* promise precision → narrower delivery windows
* operational reliability → lower late-delivery risk

This stage transforms predicted uncertainty into decision-level evaluation.

Specifically, it will:

* define multiple promise policies
* apply those policies to validation and test predictions
* compute policy-level metrics
* visualize the trade-off curve
* save artifacts used in the final analysis

No new predictive models should be trained in this stage.

# Deliverables

Implement:

```
src/evaluate_policy.py
```

Update:

```
config/model_config.yaml
```

The script consumes artifacts from the previous stage:

```
artifacts/quantile_model/
    interval_predictions_val.csv
    interval_predictions_test.csv
```

and produces:

```
artifacts/
  policy_analysis/
      policy_metrics_val.csv
      policy_metrics_test.csv
      policy_predictions_test.csv
      tradeoff_plot_val.png
      policy_summary.json
```

Create directories if they do not exist.

# Conceptual Goal

The previous stage produced uncertainty estimates via quantile regression.

This stage answers the business question:

- How should that uncertainty be translated into a buyer-facing delivery promise?

A policy converts predicted quantiles into a delivery interval shown to the buyer.

Example:

| Policy       | Promise interval | UX       | Operational risk |
| ------------ | ---------------- | -------- | ---------------- |
| Aggressive   | narrow           | good     | risky            |
| Balanced     | medium           | moderate | moderate         |
| Conservative | wide             | worse    | safer            |

The purpose of this stage is to make that trade-off measurable.

# Validation vs Test Usage

Policy selection should follow standard ML evaluation principles.

Validation split

Used to:

* compare policies
* build the trade-off plot
* select a reference policy

Test split

Used to:

* report final metrics
* confirm performance of the selected policy

All policy metrics must therefore be computed for both splits.

# Policy Definition

A policy defines:

```
promise_start
promise_end
```

using predicted quantiles.

Example:

```
balanced_policy:
  lower = q50
  upper = q90
```

Minimum supported policies:

| Policy       | Lower | Upper |
| ------------ | ----- | ----- |
| aggressive   | q50   | q85   |
| balanced     | q50   | q90   |
| conservative | q50   | q95   |

However, policies must only be evaluated if their required quantiles exist.

# Optional Baseline Policy

To provide a heuristic reference, optionally include:

```
upper_only_q90:
  lower = q50
  upper = q90
```

or

```
symmetric_fixed_width:
  lower = q50 - w/2
  upper = q50 + w/2
```

These policies are optional but useful for comparison.

# Configuration Requirements

Extend `config/model_config.yaml`.

Example:

```yaml
target_column: lead_time_minutes

artifacts:
  quantile_model_dir: artifacts/quantile_model
  policy_analysis_dir: artifacts/policy_analysis

policy_evaluation:

  validation_predictions_path: artifacts/quantile_model/interval_predictions_val.csv
  test_predictions_path: artifacts/quantile_model/interval_predictions_test.csv

  policies:
    - name: balanced_q50_q90
      lower_quantile: 0.50
      upper_quantile: 0.90

    - name: conservative_q50_q95
      lower_quantile: 0.50
      upper_quantile: 0.95

    - name: aggressive_q50_q85
      lower_quantile: 0.50
      upper_quantile: 0.85

  selection:
    max_late_delivery_rate: 0.10
    fallback: lowest_late_rate

  plot:
    annotate_points: true
    figsize: [8,6]
```

Rules:

* only evaluate policies whose required quantile columns exist
* log skipped policies explicitly
* fail only if no valid policies remain

# Prediction File Assumptions

Prediction files contain at least:

```
actual_lead_time_minutes
pred_q50
pred_q90
split
```

They may also contain additional quantiles:

```
pred_q85
pred_q95
```

This stage must recompute policy metrics directly from quantile columns, not rely on the previous stage's interval columns.

# Implementation Requirements

`src/evaluate_policy.py` must include:

* module docstring
* CLI entry point
* configuration loading
* policy validation
* metric computation
* plot generation
* artifact saving

# Pipeline Steps

## 1. Load configuration

Load `config/model_config.yaml`.

Validate:

* prediction file paths exist
* policy definitions are valid
* lower quantile < upper quantile

Fail clearly if invalid.

# 2. Load prediction files

Load:

```
validation_predictions
test_predictions
```

Validate presence of:

```
actual target column
predicted quantile columns
```

# 3. Quantile → column mapping

Implement helper:

```
quantile_to_column_name(0.90) → pred_q90
quantile_to_column_name(0.95) → pred_q95
```

Implementation suggestion:

```
int(round(q * 100))
```

to avoid float formatting issues.

# 4. Resolve valid policies

For each configured policy:

1. determine required quantile columns
2. check column existence
3. include or skip policy accordingly

Log skipped policies and reasons.

Fail only if no valid policies remain.

# 5. Compute policy-level predictions

For each policy:

```
promise_start = predicted lower quantile
promise_end   = predicted upper quantile
interval_width = promise_end - promise_start
```

Diagnostics:

* count rows where `promise_end < promise_start`
* enforce:

```
promise_end = max(promise_end, promise_start)
```

# 6. Compute row-level outcome flags

Per row:

```
is_late = actual > promise_end
is_within_interval = promise_start <= actual <= promise_end
is_early_relative_to_start = actual < promise_start
```

These are used for aggregation.

# 7. Row filtering rules

Metrics must be computed only on rows where:

* actual target exists
* required quantile predictions exist

Each policy must record:

```
n_rows_used
```

# 8. Compute core policy metrics

For each policy and split compute:

### Late delivery rate

```
mean(actual > promise_end)
```

Primary operational risk metric.

### Average interval width

```
mean(promise_end - promise_start)
```

Proxy for buyer-facing uncertainty.

### Empirical coverage

```
mean(promise_start <= actual <= promise_end)
```

Diagnostic metric.

### Early-before-start rate

```
mean(actual < promise_start)
```

Useful interpretation metric.

### Average interval bounds

```
avg_promise_start
avg_promise_end
```

Optional but recommended.

# 9. Build policy metrics table

Create tables:

```
policy_metrics_val.csv
policy_metrics_test.csv
```

Columns:

```
policy_name
lower_quantile
upper_quantile
avg_interval_width
late_delivery_rate
coverage
early_before_start_rate
avg_promise_start
avg_promise_end
n_rows_used
```

Add convenience fields:

```
late_rate_rank
width_rank
pareto_efficient
```

Pareto-efficient policies are those not dominated by another policy that is both:

* narrower
* safer

# 10. Save row-level policy predictions

Save test split predictions in long format:

```
policy_predictions_test.csv
```

Columns:

```
policy_name
actual_lead_time_minutes
promise_start
promise_end
interval_width
is_late
is_within_interval
```

# 11. Create trade-off plot

Main visualization:

Scatter plot

```
x-axis = avg_interval_width
y-axis = late_delivery_rate
```

Each point = one policy.

Use validation metrics.

Annotate points with policy names.

Save:

```
tradeoff_plot_val.png
```

# 12. Reference policy selection

Select a reference policy using validation metrics.

Rule:

1. Filter policies with

```
late_delivery_rate <= threshold
```

2. Among those choose the policy with smallest interval width

3. If none satisfy threshold:

```
select policy with lowest late rate
```

This rule must be transparent and heuristic.

# 13. Save summary JSON

Save:

```
policy_summary.json
```

Example:

```json
{
  "evaluated_policies": ["balanced_q50_q90"],
  "skipped_policies": {
    "aggressive_q50_q85": "missing column pred_q85"
  },
  "reference_policy": "balanced_q50_q90",
  "validation_metrics": {...},
  "test_metrics": {...}
}
```

# Reproducibility

This stage must be deterministic.

No randomness.

Given the same inputs and config, outputs must be identical.

# Error Handling

Handle clearly:

* missing prediction files
* missing target column
* invalid quantile mapping
* no valid policies
* artifact directory creation failure

Prefer readable error messages.

# Coding Style

Use:

* pandas
* numpy
* matplotlib
* yaml
* json
* pathlib

Avoid:

* dashboard frameworks
* optimization libraries
* interactive plotting frameworks

The implementation should remain clear and reviewable.

# Acceptance Criteria

This stage is complete when:

* `src/evaluate_policy.py` is implemented
* policies are read from config
* policies are validated against available quantiles
* policy metrics are computed for validation and test
* metrics tables are saved
* test policy predictions are saved
* trade-off plot is generated
* summary JSON is saved
* outputs are deterministic

# Key Concept Reminder

This stage implements the decision layer.

The pipeline now becomes:

```
Previous stage → Predict uncertainty (quantiles)
This stage → Evaluate decision policies using that uncertainty
```

This separation between prediction and decision policy is a core design idea in delivery promise optimization systems.
