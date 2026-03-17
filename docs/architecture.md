# System Architecture

## 1. Overview

The delivery promise system operates as an end-to-end pipeline that transforms raw operational data into a buyer-facing delivery interval.

The architecture is composed of two main layers:

- Offline pipeline: data processing, feature engineering, model training
- Online pipeline: real-time inference and policy decision

This separation ensures:

- scalability
- reproducibility
- low-latency predictions

## 2. High-Level Flow

### Offline

Raw data → Feature engineering → Training → Model registry

### Online

Checkout request → Feature retrieval → Model inference → Policy → Promise

## 3. Offline Pipeline

The offline pipeline is responsible for building and maintaining the predictive models.

### 3.1 Data Sources

Data is collected from multiple systems:

- order events (checkout, delivery)
- seller data (category, performance)
- courier events (pickup, delivery)
- geographic and temporal signals

### 3.2 Feature Engineering

Features are constructed from raw data:

- aggregation (historical prep times)
- temporal features (hour, weekday)
- geographic features (distance proxies)
- operational indicators (load, delays)

These features are stored in a feature store for reuse.

### 3.3 Model Training

Models are trained using historical data:

- point prediction model (baseline)
- quantile models (primary)

Training includes:

- time-based validation
- hyperparameter tuning
- evaluation on holdout data

### 3.4 Model Registry

Trained models are versioned and stored in a registry:

- model artifacts
- training configuration
- evaluation metrics

This enables:

- reproducibility
- rollback
- controlled deployment

## 4. Online Pipeline

The online pipeline generates delivery promises in real time during checkout.

### 4.1 Request Flow

1. User initiates checkout
2. System gathers available features
3. Model predicts lead time quantiles
4. Policy layer generates interval
5. Interval is returned to the frontend

### 4.2 Feature Retrieval

Features are retrieved from:

- real-time systems (order context)
- feature store (historical aggregates)

Latency constraints require:

- fast lookup (low milliseconds)
- precomputed features when possible

### 4.3 Model Inference

The model predicts:

- $Q_{10}$, $Q_{25}$, $Q_{50}$, $Q_{80}$, $Q_{90}$, $Q_{95}$

Inference must be:

- low latency (tens of milliseconds)
- horizontally scalable

### 4.4 Policy Layer

The policy converts predictions into:

$[a_i, b_i]$

This layer is:

- lightweight
- configurable
- independent from model training

## 5. Scalability Considerations

The system must handle high request volumes during peak traffic.

Key strategies:

- stateless inference services
- horizontal scaling (autoscaling)
- caching of frequent features
- precomputation of heavy features

## 6. Latency Constraints

The system operates in a user-facing checkout flow, requiring:

- low end-to-end latency
- predictable response times

Optimizations include:

- efficient feature retrieval
- lightweight models (e.g., tree-based)
- avoiding complex simulations at inference time

## 7. Versioning and Deployment

### 7.1 Model Versioning

Each model version includes:

- training data snapshot
- feature definitions
- hyperparameters

### 7.2 Deployment Strategy

Deployment options:

- batch rollout
- canary deployment
- A/B testing

This allows safe iteration and evaluation.

## 8. Monitoring

Monitoring is critical to ensure system reliability.

### 8.1 Operational Metrics

- late delivery rate
- early delivery rate
- on-time rate

### 8.2 Model Metrics

- MAE / RMSE
- calibration of quantiles
- coverage

### 8.3 Drift Detection

Monitor:

- feature distribution drift
- target drift (lead time changes)

Triggers:

- model retraining
- recalibration

### 8.4 Alerting

Alerts are triggered when:

- late delivery rate exceeds threshold
- coverage deviates from expected
- system latency increases

## 9. Retraining Strategy

Models are retrained periodically:

- scheduled retraining (e.g., daily / weekly)
- triggered retraining (based on drift)

Pipeline includes:

- data ingestion
- feature recomputation
- model retraining
- validation
- deployment

## 10. Design Choices and Trade-offs

### Simplicity vs Accuracy

- tree-based models chosen for speed and robustness
- more complex models deferred

### Precomputation vs Real-Time Features

- precompute heavy features offline
- compute lightweight features online

### Prediction vs Decision Separation

- model predicts uncertainty
- policy defines business trade-offs

This separation improves:

- flexibility
- maintainability

## 11. Extensions

Potential future improvements:

- dynamic policy selection per order
- integration with dispatch optimization
- feedback loops from delivery outcomes
- tighter integration with courier assignment systems

## 12. Summary

The architecture separates:

- offline learning (data → model)
- online decision-making (request → promise)

This design ensures:

- scalability
- low latency
- flexibility in policy control
- robustness through monitoring and retraining

and provides a realistic foundation for a production delivery promise system.