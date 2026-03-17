# Problem Framing

## 1. Business Context

In a marketplace logistics platform such as Mercado Envíos, the buyer is shown a delivery promise interval during checkout:

```text
"Delivery today between 16:00 and 20:00"
```

This promise is a critical component of the user experience, as it directly impacts:

- Conversion rate (narrower intervals are more attractive)
- Customer satisfaction (late deliveries degrade trust)
- Operational reliability (tight promises are harder to fulfill)

The system must generate this promise before fulfillment begins, under uncertainty about multiple operational factors.

This creates a fundamental trade-off:

- Narrow intervals: better user experience, higher risk of late deliveries
- Wide intervals: safer operationally, worse user experience

Therefore, the problem is not only predictive, but also decision-making under uncertainty.

## 2. Problem Statement

For each order $i$, the system must output a delivery promise interval:

$[a_i, b_i]$

where:

- $a_i$: promised start time (minutes from checkout)
- $b_i$: promised end time

Let:

$T_i$ = actual delivery lead time (minutes)

The system must choose $[a_i, b_i]$ such that it balances:

- Reliability: low probability of late delivery $(T_i > b_i)$
- Precision: small interval width $(b_i - a_i)$

## 3. Inputs, Outputs, and Relevant Variables

The system can be formalized as a function:

$f: X_i \rightarrow [a_i, b_i]$

### Inputs

$X_i$

Represents all information available at checkout time, including:

- seller characteristics
- order attributes
- temporal context (time of day, day of week)
- geographic information
- operational state (courier availability, system load)

### Target Variable

$T_i$ = actual delivery lead time

This is the variable to be predicted during training.

### Outputs

$[a_i, b_i]$

The delivery promise interval shown to the buyer, where:

- $a_i$: start of the promise window
- $b_i$: end of the promise window

### Relevant Variables

The most important variables for modeling include:

**Seller-side**
- preparation time distribution
- reliability / historical performance
- seller category

**Order-level**
- item type
- order size
- priority / urgency signals

**Temporal**
- hour of day
- day of week

**Geographic**
- distance
- location density
- traffic proxies

**Operational**
- courier load
- system congestion

These variables influence both the expected value and the uncertainty of delivery time.

## 4. Decomposition of Lead Time

The total lead time is composed of multiple operational components:

$T_i = T_i^{prep} + T_i^{pickup} + T_i^{delivery}$

Where:

- $T_i^{prep}$: seller preparation time
- $T_i^{pickup}$: delay until courier pickup
- $T_i^{delivery}$: last-mile delivery duration

Some of these components are not directly observable, which introduces additional uncertainty into the system.

## 5. Predictive Component

The predictive task is to estimate the conditional distribution of lead time:

$P(T_i \mid X_i)$

This can be approximated through:

### Point Estimation

$\mathbb{E}[T_i \mid X_i]$

### Quantile Estimation

$Q_q(T_i \mid X_i)$

Quantile estimation is particularly useful because it enables direct construction of prediction intervals, which align naturally with the product requirement.

## 6. Decision Component

The delivery promise shown to the buyer is not the raw prediction, but a decision derived from the predicted distribution.

A policy $\pi$ maps predictions into an interval:

$[a_i, b_i] = \pi(X_i)$

A simple and effective policy is to use quantiles:

$[a_i, b_i] = [Q_{\alpha}(T_i \mid X_i), Q_{\beta}(T_i \mid X_i)]$

with $\alpha < \beta$.

Examples:

- Conservative: $[Q_{0.10}, Q_{0.95}]$
- Balanced: $[Q_{0.10}, Q_{0.90}]$
- Aggressive: $[Q_{0.10}, Q_{0.80}]$

This explicitly separates:

- Prediction: modeling uncertainty
- Decision: choosing business trade-offs

## 7. Objective Function

The problem can be formulated as a constrained optimization problem:

Minimize:

$\mathbb{E}[b_i - a_i]$

Subject to:

$P(T_i > b_i) \leq \epsilon$

Where:

- $b_i - a_i$: interval width (user experience)
- $P(T_i > b_i)$: late delivery probability
- $\epsilon$: acceptable late rate threshold

Alternatively, this can be expressed as a cost function:

$\mathcal{L} = \lambda_1 \cdot (b_i - a_i) + \lambda_2 \cdot \mathbb{I}(T_i > b_i)$

This formulation makes explicit the trade-off between:

- precision (narrow intervals)
- reliability (on-time delivery)

## 8. ML Problem Definition

This problem can be framed as a supervised learning task with a probabilistic component:

- Input: $X_i$
- Target: $T_i$

Rather than predicting a single value, the objective is to estimate the distribution of outcomes, which enables decision-making under uncertainty.

This justifies the use of:

- regression models (for point estimates)
- quantile regression models (for interval estimation)
- or more generally, probabilistic models

Compared to heuristic approaches (e.g., fixed delivery windows), an ML-based approach:

- adapts to context-specific variability
- captures heterogeneity across sellers and orders
- enables dynamic trade-off optimization

## 9. Key Trade-offs

The system must navigate several trade-offs:

### Precision vs Reliability
- Narrow intervals improve user experience but increase late deliveries

### Early vs Late Deliveries
- Early deliveries may create waiting friction
- Late deliveries strongly degrade trust

### Calibration vs Sharpness
- Well-calibrated intervals should match empirical coverage
- Sharp intervals should be as narrow as possible

## 10. Why This is a Decision Problem (Not Just Prediction)

A standard regression model is insufficient because:

- The goal is not to predict $T_i$, but to choose a promise interval
- Different business strategies require different trade-offs
- The optimal decision depends on risk tolerance

Therefore, the system must explicitly separate:

- Uncertainty estimation (ML problem)
- Policy optimization (decision problem)

## 11. Summary

This problem can be summarized as:

Estimate uncertainty in delivery lead time and transform it into a buyer-facing promise interval that balances operational reliability and user experience.

This requires combining:

- Predictive modeling (to estimate P($T_i$ | $X_i$))
- Decision policies (to select intervals under business constraints)