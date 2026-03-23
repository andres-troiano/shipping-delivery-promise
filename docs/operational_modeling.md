# Operational Modeling: Seller Preparation Timing

## 1. Overview

In addition to estimating delivery lead time and constructing a buyer-facing promise interval, a production system may also control when to notify the seller to begin preparing the order.

This introduces a second decision problem:

- buyer-facing decision: delivery promise interval
- operational decision: seller release timing

The prototype focuses on the first. This document outlines how the second could be modeled and integrated.

## 2. Problem Definition

For each order $i$, the system observes features $X_i$ at checkout and must determine:

- seller release time $r_i$: when preparation should begin
- promise interval $[a_i, b_i]$: what is shown to the buyer

Conceptually:

$X_i → (r_i, [a_i, b_i])$

The goal is to coordinate preparation, pickup, and delivery so that:

- deliveries occur within the promised interval
- orders are not prepared significantly earlier than pickup

## 3. Process Decomposition

Delivery lead time can be decomposed into components:

```text
lead_time =
    preparation_time
  + pickup_delay
  + delivery_duration
```

A more explicit temporal formulation is:

$T_i = r_i + P_i + W_i + D_i$

Where:

- $r_i$: delay from checkout to seller notification
- $P_i$: preparation duration
- $W_i$: waiting or pickup-related delay after preparation
- $D_i$: last-mile delivery duration

The preparation-complete event is typically not directly observed, which makes component-level modeling non-trivial.

## 4. Modeling Approaches

Because preparation completion is unobserved, two main approaches can be considered.

### 4.1 Proxy Supervision

Estimate preparation behavior indirectly using observable signals.

Examples of proxy signals:

- seller category and historical behavior
- residual lead time after accounting for transport
- patterns of delay before pickup

A proxy target can be constructed as:

```text
prep_proxy ≈ lead_time − delivery_duration − pickup_baseline
```

This proxy is noisy but allows supervised modeling of preparation variability.

Characteristics:

- simple and practical
- uses existing data
- limited by proxy quality

### 4.2 Latent Variable Modeling

Treat preparation time as a hidden variable in a multi-stage probabilistic model.

Conceptually:

```text
lead_time = prep_time + pickup_delay + delivery_duration
```

where `prep_time` is not observed but inferred from data.

This can be approached using:

- hierarchical probabilistic models
- state-space formulations
- expectation-based inference

Characteristics:

- more principled
- separates sources of uncertainty
- higher complexity and implementation cost

## 5. Seller Release Policy

Given estimates of preparation and pickup timing, seller notification can be framed as a just-in-time scheduling problem.

### 5.1 Point Estimate Policy

$r_i$ = expected_pickup_time − expected_prep_time

This aligns preparation completion with expected pickup.

### 5.2 Uncertainty-Aware Policy

Using quantile estimates:

$r_i$ = pickup_quantile − prep_quantile

For example:

- conservative prep estimate (high quantile)
- moderate pickup estimate

This reduces the risk that the order is not ready at pickup time.

### 5.3 Practical Constraints

- $r_i ≥ 0$ (cannot release before checkout)
- upper bounds on delay to avoid excessive latency
- category-specific adjustments (e.g., food vs non-perishables)

## 6. Objective Trade-offs

Seller release timing introduces an additional trade-off beyond the buyer-facing promise.

The system must balance:

- late delivery risk
- interval width (user experience)
- waiting time after preparation (operational efficiency)

A conceptual objective:

$L_i$ = $λ_1$ $(b_i − a_i)$ + $λ_2$ $I(T_i > b_i)$ + $λ_3$ $\text{waiting_time_i}$

Where:

- $λ_1$: penalizes wide intervals
- $λ_2$: penalizes late deliveries
- $λ_3$: penalizes orders prepared too early

Relative importance may vary by category.

## 7. Practical Constraints

Several constraints limit direct implementation:

- preparation completion is not directly observed
- pickup timing depends on external dispatch systems
- limited visibility into courier assignment and routing
- synthetic dataset does not include real operational signals

These constraints motivate simplified or proxy-based approaches.

## 8. Relationship with Current Prototype

The current prototype:

- models total lead time as a single stochastic target
- does not explicitly estimate preparation or pickup components
- does not optimize seller release timing

Instead, preparation and pickup effects are absorbed into:

```text
prep_time_minutes
pickup_delay_minutes
```

This is sufficient for constructing buyer-facing promise intervals, but not for just-in-time scheduling.

## 9. Summary

Seller preparation timing introduces a second decision layer:

- when to start preparation
- how to construct the buyer promise

The prototype addresses the second directly.
A full production system would model both jointly, using component-level predictions and uncertainty-aware scheduling.

This extension transforms the problem from pure prediction into a coordination problem across multiple stages of the delivery process.
