# Assumptions and Risks

## 1. Overview

This solution is built under a set of simplifying assumptions due to:

- lack of real production data
- absence of full system observability
- constraints of a prototype implementation

These assumptions enable tractability but introduce risks that must be understood and mitigated.

---

## 2. Data Assumptions

### 2.1 Proxy Dataset Validity

Assumption:

- The constructed dataset (real trip durations + synthetic features) approximates real delivery dynamics.

Risk:

- Synthetic components may not reflect real-world variability
- interactions between variables may be unrealistic

Mitigation:

- validate distributions against real data when available
- gradually replace synthetic features with real signals

---

### 2.2 Feature Availability at Checkout

Assumption:

- All features used in the model are available at prediction time.

Risk:

- some features may only be known after checkout
- feature leakage could occur during training

Mitigation:

- enforce strict feature availability constraints
- design features explicitly for inference-time availability

---

### 2.3 Data Quality

Assumption:

- historical data is clean, consistent, and correctly timestamped.

Risk:

- missing or noisy data
- incorrect timestamps or event ordering

Mitigation:

- data validation pipelines
- anomaly detection and filtering

---

## 3. Modeling Assumptions

### 3.1 Lead Time Decomposition

Assumption:

$T_i$ = prep + pickup + delivery

Risk:

- components may not be independent
- hidden factors may influence multiple components

Mitigation:

- allow models to learn interactions implicitly
- consider joint modeling approaches in the future

---

### 3.2 Stationarity

Assumption:

- relationships between features and lead time remain stable over time.

Risk:

- demand shifts
- seasonality changes
- operational policy changes

Mitigation:

- frequent retraining
- monitoring for drift

---

### 3.3 Quantile Model Calibration

Assumption:

- predicted quantiles are well-calibrated.

Risk:

- miscalibration leads to:
  - higher-than-expected late delivery rates
  - unreliable intervals

Mitigation:

- calibration monitoring
- conformal prediction as a correction layer

---

## 4. Operational Assumptions

### 4.1 Static Policy

Assumption:

- a fixed policy $(α, β)$ is applied to all orders.

Risk:

- suboptimal decisions for different contexts
- over-conservative or overly aggressive behavior

Mitigation:

- dynamic policies based on uncertainty or context

---

### 4.2 Independence of Orders

Assumption:

- each order can be treated independently.

Risk:

- system-level congestion effects
- interactions between orders

Mitigation:

- incorporate system-level features (e.g., courier load)
- consider simulation-based approaches

---

### 4.3 Immediate Policy Execution

Assumption:

- once the promise is generated, it is not updated.

Risk:

- real-world delays are not communicated
- inability to correct incorrect predictions

Mitigation:

- introduce dynamic updates or notifications
- provide revised ETAs during delivery

---

## 5. System Assumptions

### 5.1 Low-Latency Inference

Assumption:

- models can produce predictions within strict latency constraints.

Risk:

- feature retrieval bottlenecks
- model complexity affecting response time

Mitigation:

- optimize feature store
- use efficient models
- precompute heavy features

---

### 5.2 Reliable Monitoring

Assumption:

- monitoring systems detect issues promptly.

Risk:

- delayed detection of drift or failures
- silent degradation of performance

Mitigation:

- define clear alert thresholds
- implement automated checks

---

## 6. Key Risks

### 6.1 Distribution Shift

- changes in demand patterns
- new sellers or regions
- external shocks (weather, events)

Impact:

- degraded model performance
- increased late deliveries

---

### 6.2 Cold Start

- new sellers with no history
- new geographic areas

Impact:

- unreliable predictions

Mitigation:

- fallback to global averages
- hierarchical modeling

---

### 6.3 Misalignment with Business Objectives

- incorrect cost weighting
- suboptimal policy selection

Impact:

- poor trade-off between UX and reliability

Mitigation:

- iterative tuning
- A/B testing

---

## 7. Limitations of the Prototype

- simplified dataset construction
- limited feature richness
- absence of real-time operational signals
- no integration with dispatch or routing systems

These limitations mean that results should be interpreted as:

> a conceptual validation of the approach, not a production-ready system.

---

## 8. Summary

This solution relies on several assumptions to simplify a complex real-world system.

Key risks include:

- data mismatch
- model miscalibration
- distribution shift
- operational complexity

However, with proper monitoring, retraining, and system design, these risks can be mitigated, making the approach viable for real-world deployment.