## 1. Business Context

In a marketplace logistics platform, the buyer is presented with a delivery promise such as:

```text
“Delivery today between 16:00 and 20:00.”
```

This promise plays a central role in the product experience. It directly influences conversion by shaping user expectations at checkout, and it affects trust by setting a clear commitment about when the order will arrive. When the promise is accurate and precise, it improves perceived reliability and convenience. When it fails, it leads to dissatisfaction, support interactions, and potential compensations.

A key challenge is that this promise must be issued before the delivery occurs, under uncertainty. At the moment of checkout, the system does not know the actual delivery time, only a set of features describing the order and its context.

This creates an inherent trade-off. Narrow promise intervals are more attractive to users because they feel precise and actionable, but they increase the risk of being wrong. Wider intervals are operationally safer, but degrade the user experience by being less informative.

For this reason, the problem is not simply to predict delivery time. The core problem is to make a **decision under uncertainty**: how to construct a delivery promise that balances reliability and precision.

## 2. Problem Statement

For each order, the system observes a set of features available at checkout, such as buyer and seller location, seller category, time of day, and proxy variables related to distance or routing.

Let:

* T = actual delivery lead time (unknown at checkout)
* X = observed features

The system must output a promise interval:

```text
[start_time, end_time] = π(X)
```

where π is a policy that maps order features to a delivery promise.

The goal is to design π such that the promise is:

* reliable: deliveries rarely occur after the promised end time
* informative: the interval is not unnecessarily wide

## 3. Prediction and Decision Layers

This problem naturally decomposes into two layers: a prediction layer and a decision (policy) layer.

### Prediction Layer

The prediction layer estimates the uncertainty of delivery time given the observed features. Instead of predicting a single value, the system models the distribution of possible delivery times.

In this prototype, this is done using quantile regression, producing estimates such as:

* lower quantiles (e.g. q10 or q25)
* median (q50)
* upper quantiles (e.g. q90 or q95)

These quantiles provide a practical representation of uncertainty without assuming a specific distribution.

### Decision (Policy) Layer

The policy layer transforms predicted quantiles into a delivery promise.

A simple policy can be expressed as:

```text
[start_time, end_time] = [q_low(X), q_high(X)]
```

Different choices of quantiles define different policies:

* Conservative: wider intervals, lower late risk
* Balanced: moderate trade-off
* Aggressive: narrower intervals, higher risk

The key separation is:

```text
The model estimates uncertainty, while the policy encodes business trade-offs.
```

## 4. Objective and Trade-offs

The system must balance three competing factors.

First, late deliveries occur when the actual delivery time exceeds the promised end time. These events are highly undesirable because they directly impact customer satisfaction and generate operational costs such as support interactions and compensations.

Second, early deliveries occur when the order arrives before the promised start time. While less critical than late deliveries, they reduce the credibility and usefulness of the promise by making the interval less meaningful.

Third, the width of the interval determines how informative the promise is. Narrow intervals improve the user experience by providing precise expectations, while wide intervals reduce clarity and perceived quality.

Conceptually, the goal is to minimize late deliveries while keeping the interval as narrow as possible. In practice, this trade-off is often handled through constraints rather than explicit cost functions. A common approach is to enforce a maximum acceptable late delivery rate, and within that constraint, optimize for the narrowest possible intervals.

For example, the system may aim to keep late deliveries below 10%, while making intervals as narrow as possible within that constraint.

This reflects a typical business goal: maintain **reliability guarantees** while maximizing **promise precision**.

## 5. Evaluation Metrics

To evaluate the system, we consider three key metrics.

### 1. Late Delivery Rate
Defined as the fraction of orders delivered after the promised end time. This is the primary operational KPI because it directly reflects reliability and customer impact.

### 2. Average Interval Width
Measures how informative the promise is. Smaller widths correspond to better user experience, as they provide more precise expectations.

### 3. Coverage
Defined as the fraction of deliveries that fall within the promised interval. This metric is useful for assessing whether the predicted intervals are well calibrated, although it is secondary to the late delivery rate from a business perspective.

## 6. Primary Business KPI

The most important KPI for this system is the **late delivery rate**, defined as the percentage of orders delivered after the promised end time.

This metric directly affects:

- customer satisfaction
- operational cost (refunds, support)
- trust in the platform

Other metrics, such as interval width and coverage, are optimized subject to maintaining acceptable levels of late deliveries.

## 7. Seller Preparation Timing

In real marketplace systems, the platform may also control when the seller is notified to begin preparing the order.

This introduces a **second decision layer**:

* triggering preparation earlier reduces delivery risk but may create inefficiencies
* triggering it later improves efficiency but increases the risk of delays

In this prototype, preparation time is treated as part of the stochastic delivery process. In a production system, it could be explicitly modeled and jointly optimized with the delivery promise.

## 8. Key Challenges

Several factors make this problem challenging in practice. Delivery time is a stochastic process composed of multiple stages, some of which may not be directly observed, such as seller preparation time. Different seller categories exhibit very different behaviors, leading to heterogeneous distributions. The system must operate in real time at checkout, which imposes latency constraints. Finally, the trade-offs involved are driven by business considerations, not purely by predictive accuracy.

## 9. Scope of the Prototype

This prototype focuses on:

* modeling delivery uncertainty using quantile regression
* defining interval-based promise policies
* evaluating trade-offs between reliability and precision

It does not include:

* customer conversion modeling
* dynamic courier assignment or routing
* real-time dispatch optimization
* explicit optimization of seller-side decisions

These aspects are important in a full production system but are outside the scope of this simplified implementation.

## 10. Alternative Approaches

While this prototype uses quantile regression and rule-based policies, several alternative approaches could be considered in a production system.

These include:

- Probabilistic models that estimate full predictive distributions (NGBoost, distributional regression, Bayesian regression)
- Conformal prediction to produce calibrated intervals with statistical guarantees, independent of the underlying model
- Simulation-based logistics models to explicitly model system dynamics such as preparation, pickup, and delivery stages
- Reinforcement learning to directly optimize decision policies under uncertainty, potentially incorporating long-term operational effects
- Constrained optimization: the problem can be formulated as minimizing interval width subject to a constraint on late delivery rate. This provides a clean theoretical framework, but in practice requires defining differentiable objectives and reliable calibration.
- Cost-based optimization: define an explicit business loss function that penalizes late deliveries and wide intervals. This approach depends on estimating business costs, which may be difficult in practice.

These approaches differ in complexity, interpretability, and operational requirements, and may be more suitable depending on data availability and system constraints.
