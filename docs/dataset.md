# Dataset Construction

## 1. Overview

The dataset is designed to approximate end-to-end delivery lead time in a marketplace setting, where some components of the process are not directly observed.

To address this, we construct a hybrid dataset that combines:

- a real transport proxy derived from historical trip data
- synthetic marketplace-side variables representing seller and operational behavior

This enables the creation of a dataset with structured, feature-dependent uncertainty, suitable for training probabilistic models and evaluating delivery-promise policies.

## 2. High-Level Construction

The dataset is built by combining:

Transport data → Synthetic features → Stochastic generation → Lead time target

Where:

- transport dynamics are grounded in real data
- marketplace dynamics are simulated using structured rules

## 3. Real Transport Component

The transport component is derived from the Kaggle NYC Taxi Trip Duration dataset.

From this dataset, we:

- filter invalid or unrealistic trips
- compute `delivery_duration_minutes` as a proxy for last-mile travel time
- derive `trip_distance_km` from geographic coordinates
- extract temporal features:

  - `hour_of_day`
  - `day_of_week`
  - `month`
  - `is_weekend`
  - `is_peak_hour`

This component captures realistic spatial and temporal variability in delivery duration.

## 4. Synthetic Marketplace Features

To model sources of uncertainty not present in the data, we generate synthetic features representing seller, order, and operational conditions.

### 4.1 Seller Features

- `seller_category`
- `seller_reliability`
- `seller_avg_prep_minutes`

### 4.2 Order Features

- `order_size`
- `priority_flag`
- `is_high_complexity_order`

### 4.3 Operational Features

- `courier_load`

These variables introduce heterogeneity across orders and act as drivers of variability in lead time.

## 5. Structured Stochastic Generation

The unobserved components of delivery time are generated using structured stochastic rules, where both the expected value and variability depend on input features.

### 5.1 Preparation Time

`prep_time_minutes` is generated from:

- a base distribution conditioned on `seller_category`
- adjusted by:

  - increasing with `order_size`
  - increasing with `is_high_complexity_order`
  - increasing during `is_peak_hour`
  - increasing when `seller_reliability` is low
  - slightly decreasing when `priority_flag` is set

Values are clipped to configured bounds.

### 5.2 Pickup Delay

`pickup_delay_minutes` is generated from:

- a base delay distribution
- adjusted by:

  - increasing with `courier_load`
  - increasing during `is_peak_hour`
  - increasing when `seller_reliability` is low

Values are clipped to configured bounds.

### 5.3 Transport Adjustment

A modest congestion effect is applied to `delivery_duration_minutes` during peak hours to reflect increased travel time.

## 6. Target Definition

The final target variable is defined as:

```text
lead_time_minutes =
    prep_time_minutes
  + pickup_delay_minutes
  + delivery_duration_minutes
```

This formulation models delivery time as the sum of multiple stochastic components.

## 7. Dataset Properties

The resulting dataset exhibits:

- Heteroskedasticity: Variability depends on features such as seller category, order complexity, and time of day
- Structured uncertainty: Noise is feature-dependent rather than arbitrary
- Conditional distributions: Supports estimation of $P(T \mid X)$
- Partial realism: Transport dynamics are data-driven, while marketplace dynamics are simulated

## 8. Assumptions

The synthetic generation process relies on simplified assumptions:

- seller behavior is approximated through category and reliability
- operational load is represented by a single variable (`courier_load`)
- interactions between system components (e.g., dispatch decisions) are not modeled

These assumptions are designed to produce plausible behavior while maintaining simplicity and controllability.

## 9. Limitations

- synthetic components are not calibrated to real-world marketplace data
- system-level feedback effects are not modeled
- real-time operational dynamics are simplified

Despite these limitations, the dataset provides a controlled environment for studying uncertainty-aware prediction and policy design.

## 10. Summary

The dataset is hybrid because:

- transport behavior is grounded in real trip data
- marketplace and operational variability are simulated using structured rules

This enables the modeling of delivery lead time as a stochastic process and supports the evaluation of interval-based delivery policies.
