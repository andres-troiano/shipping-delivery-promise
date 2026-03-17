# Modeling Approach

## 1. Overview

The goal of the modeling layer is to estimate the uncertainty in delivery lead time:

$P(T_i \mid X_i)$

This distribution is then used by the policy layer to generate a delivery promise interval.

Rather than focusing only on point prediction, the modeling approach is designed to:

- capture heterogeneity across orders
- model uncertainty explicitly
- support decision-making via quantiles

## 2. Problem Type

This is a supervised learning problem with a probabilistic objective:

- Input: $X_i$
- Target: $T_i$ (continuous variable)

Two complementary formulations are considered:

### 2.1 Point Estimation (Regression)

$\hat{T}_i = \mathbb{E}[T_i \mid X_i]$

Used as:

- a baseline model
- a sanity check for feature quality

### 2.2 Quantile Estimation (Primary Approach)

$\hat{Q}_q(T_i \mid X_i)$

for multiple quantiles $q \in$ {0.10, 0.25, 0.50, 0.80, 0.90, 0.95}

This enables:

- construction of prediction intervals
- direct control over risk (late deliveries)
- flexibility in defining policies

## 3. Model Choice

### 3.1 Gradient Boosted Trees (LightGBM)

Primary model:

- LightGBM Regressor
- trained separately for each quantile

#### Why LightGBM?

- Handles tabular data effectively
- Captures non-linear interactions
- Robust to feature scaling
- Efficient training and inference
- Strong performance with limited tuning

#### Why separate quantile models?

- Simple and scalable
- Direct optimization via quantile (pinball) loss
- Flexible selection of quantiles for policy design

## 4. Training Strategy

### 4.1 Dataset

Since no dataset is provided, a proxy dataset is constructed combining:

- real-world trip duration data (for delivery time)
- synthetic features (for seller and operational components)

Target:

$T_i = \text{prep} + \text{pickup} + \text{delivery}$

### 4.2 Train / Validation Split

A time-based split is used:

- train: past data
- validation: future data

This simulates production conditions and avoids leakage.

### 4.3 Loss Function

For quantile models, the pinball loss is used:

![Lead time equation](assets/lead_time.png)

This directly optimizes quantile estimates.

### 4.4 Feature Engineering

Key feature types:

- categorical (seller category, item type)
- temporal (hour, weekday)
- geographic (distance proxies)
- operational (simulated load / delay)

Tree-based models reduce the need for heavy preprocessing.

## 5. Evaluation of Models

The modeling layer is evaluated independently from the policy layer.

### 5.1 Point Model Metrics

- MAE
- RMSE

Used for:

- baseline comparison
- debugging feature quality

### 5.2 Quantile Model Metrics

- Pinball loss (per quantile)
- Calibration: $P(T_i \leq \hat{Q}_q) \approx q$
- Coverage (for interval pairs)

These ensure that predicted quantiles reflect true uncertainty.

## 6. Why Quantile Regression?

Quantile regression is particularly well-suited for this problem because:

- the product requires interval outputs, not point predictions
- it provides direct control over risk (via upper quantiles)
- it avoids assumptions about the full distribution
- it integrates naturally with policy-based decision making

Compared to predicting a mean + variance:

- more robust to skewed distributions
- easier to interpret operationally

## 7. Limitations of the Approach

### 7.1 Independent Quantile Models

- may produce quantile crossing (e.g., Q90 < Q80)
- requires post-processing if severe

### 7.2 Calibration Issues

- quantiles may be miscalibrated under distribution shift
- requires monitoring and potential recalibration

### 7.3 Synthetic Data Bias

- proxy dataset may not capture real-world dynamics
- risk of overly optimistic performance

### 7.4 Lack of Temporal Dynamics

- model is not sequential
- may miss temporal dependencies (e.g., demand waves)

### 7.5 Cold Start

- new sellers or regions may lack historical signals
- requires fallback strategies (e.g., global priors)

## 8. Alternative Modeling Approaches

Several alternative approaches could improve or replace the current method:

### 8.1 Probabilistic Models

Examples: NGBoost, Gaussian processes

- model full distribution
- provide uncertainty estimates directly
- strong alternative

### 8.2 Conformal Prediction

- produces calibrated intervals with guarantees
- robust to model misspecification
- complementary method

### 8.3 Simulation-Based Models

- explicitly model logistics system dynamics
- capture interactions between components
- system-level approach

### 8.4 Reinforcement Learning

- optimize policy directly
- learn trade-offs dynamically
- advanced / future approach

## 9. Summary

The modeling approach focuses on:

- estimating conditional uncertainty in delivery time
- using quantile regression as a practical and scalable solution
- enabling a policy layer to control business trade-offs

While simple, this approach provides:

- strong performance on tabular data
- interpretability
- flexibility for decision-making

and serves as a solid foundation for more advanced methods.