# Policy and Metrics

## 1. Overview

The predictive model estimates the distribution of delivery lead time:

$P(T_i | X_i)$

However, the buyer-facing output is not a prediction, but a decision:

$[a_i, b_i]$

This decision is produced by a policy layer, which transforms model outputs into a delivery promise interval.

This layer is critical because it defines the business trade-off between:

- customer experience (narrow intervals)
- operational reliability (on-time delivery)

## 2. Policy Definition

A policy π maps predicted quantiles into a promise interval:

$[a_i, b_i] = π(X_i)$

### 2.1 Quantile-Based Policies

A simple and effective class of policies is:

$[a_i, b_i] = [Q_α, Q_β]$

where:

- $Q_α$ = lower quantile (start of interval)
- $Q_β$ = upper quantile (end of interval)
- $α < β$

### 2.2 Example Policies

Different choices of $(α, β)$ produce different trade-offs:

**Conservative policy**
- $[Q_{10}, Q_{95}]$
- wide interval
- low late delivery rate

**Balanced policy**
- $[Q_{10}, Q_{90}]$
- moderate width
- moderate risk

**Aggressive policy**
- $[Q_{10}, Q_{80}]$
- narrow interval
- higher late delivery risk

### 2.3 Start Time Considerations

Using $Q_{50}$ as the start time leads to:

- ~50% of deliveries occurring before the interval
- poor alignment with user expectations

Lower quantiles (e.g., $Q_{10}$ or $Q_{25}$) provide:

- better coverage from the start
- more realistic intervals

## 3. Evaluation Metrics

Policies are evaluated based on their operational outcomes, not just predictive accuracy.

### 3.1 Late Delivery Rate (Primary Reliability Metric)

Late delivery occurs when:

$T_i > b_i$

Metric:

$P(T_i > b_i)$

Interpretation:

- measures violation of the promise
- directly impacts customer satisfaction

### 3.2 Interval Width (User Experience Metric)

Width:

$b_i - a_i$

Interpretation:

- proxy for perceived precision
- narrower intervals improve conversion

### 3.3 Coverage (Calibration Metric)

Coverage:

$P(a_i ≤ T_i ≤ b_i)$

Interpretation:

- measures whether intervals reflect true uncertainty
- ideally aligns with $(β - α)$

### 3.4 Early Delivery Rate (Optional)

Early delivery occurs when:

$T_i < a_i$

Interpretation:

- may create waiting friction
- generally less harmful than late delivery

## 4. Business KPI and Trade-off

The core business trade-off is:

- minimize late deliveries
- minimize interval width

These objectives are inherently conflicting.

### 4.1 Pareto Frontier

Each policy corresponds to a point:

- x-axis: average interval width
- y-axis: late delivery rate

The set of optimal policies forms a Pareto frontier, where:

- no policy can improve one metric without worsening the other

### 4.2 Policy Selection

A final policy must be selected based on business priorities.

Options include:

- fixed late-rate threshold (e.g., ≤ 10%)
- cost-based optimization
- experimentation (A/B testing)

## 5. Cost-Based Formulation (Optional Extension)

The decision problem can be expressed as:

$L = λ₁ · (b_i - a_i) + λ₂ · 𝟙(T_i > b_i)$

Where:

- λ₁: cost of wider intervals (conversion loss)
- λ₂: cost of late deliveries (customer dissatisfaction)

This enables:

- explicit trade-off tuning
- alignment with business KPIs

## 6. Policy Evaluation Framework

Policies are evaluated on a validation dataset:

For each policy:

1. generate interval $[a_i, b_i]$
2. compute metrics:
   - late delivery rate
   - average width
   - coverage
3. compare across policies

## 7. Limitations

### 7.1 Static Policies

- same $(α, β)$ applied to all orders
- may not adapt to varying uncertainty levels

### 7.2 Dependence on Calibration

- poorly calibrated quantiles lead to:
  - unexpected late rates
  - unreliable intervals

### 7.3 Metric Trade-offs Not Explicitly Optimized

- evaluation is retrospective
- no guarantee of optimal policy

## 8. Extensions

### 8.1 Dynamic Policies

- choose $(α, β)$ per order
- based on uncertainty or context

### 8.2 Conformal Calibration

- enforce coverage guarantees
- improve reliability

### 8.3 Context-Aware Cost Functions

- vary λ₁ and λ₂ by:
  - user segment
  - seller type
  - time of day

---

## 9. Summary

The policy layer transforms uncertainty estimates into business decisions.

It enables:

- explicit control over trade-offs
- interpretable decision-making
- flexible system design

By separating prediction from decision, the system can:

- improve models independently
- adjust policies without retraining