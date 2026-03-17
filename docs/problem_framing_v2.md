## 1. Business Context

In a marketplace logistics platform, the buyer is shown a delivery promise such as:

- “Delivery today between 16:00 and 20:00.”

This promise is a core part of the product experience because it:

* influences conversion rate
* sets customer expectations
* affects trust and satisfaction

However, the promise must be issued before the delivery happens, under uncertainty.

This creates a fundamental trade-off:

* Narrow intervals → better user experience, but higher risk of being wrong
* Wide intervals → safer operationally, but worse user experience

Therefore, the problem is not simply to predict delivery time.
The real problem is:

- How to choose a delivery promise under uncertainty.

## 2. Problem Statement

For each order, we observe a set of features available at checkout, such as:

* buyer and seller location
* seller category (restaurant, supermarket, etc.)
* time of day / day of week
* estimated distance or routing features

Let:

* T = actual delivery lead time (unknown at checkout)
* X = observed features

The system must output a promise interval:

- [start_time, end_time]

This interval is shown to the user.

The goal is to design a system that, given X:

* produces a reliable promise (rarely late)
* keeps the interval as informative (narrow) as possible

## 3. Prediction vs Decision

This problem naturally separates into two layers:

### 3.1 Prediction Layer (Modeling)

Estimate the uncertainty of delivery time:

- What is the distribution of delivery time given the order features?

In this prototype, this is approximated using quantile regression, producing:

* lower quantiles (e.g. 10th percentile)
* median (50th percentile)
* upper quantiles (e.g. 90th, 95th percentile)

These quantiles describe the uncertainty of delivery time.

### 3.2 Decision Layer (Policy)

Transform model outputs into a promise shown to the user.

Example:

* start_time = lower quantile (e.g. q10 or q25)
* end_time = upper quantile (e.g. q90 or q95)

Different choices define different policies:

| Policy       | Behavior                               |
| ------------ | -------------------------------------- |
| Conservative | wider intervals, fewer late deliveries |
| Balanced     | moderate trade-off                     |
| Aggressive   | narrower intervals, higher risk        |

Key idea:

* The model estimates uncertainty.
* The policy encodes business trade-offs.

## 4. Objective

The system must balance three competing factors:

### 4.1 Late Deliveries (Reliability)

* Happens when delivery occurs after the promised end time
* Directly impacts:

  * customer dissatisfaction
  * support tickets
  * refunds / compensations

### 4.2 Early Deliveries (Credibility)

* Happens when delivery occurs before the promised start time
* Reduces the usefulness of the promise
* Makes the interval less meaningful

### 4.3 Interval Width (User Experience)

* Wider intervals are less informative
* Narrow intervals improve perceived precision and convenience

### Combined Objective

Conceptually, the system aims to:

- Minimize late deliveries while keeping the promise interval as narrow as possible

## 5. Constraint-Based Formulation

In practice, this problem is often handled using constraints.

A common formulation is:

- Minimize average interval width
- subject to a maximum acceptable late delivery rate

Example:

* Late delivery rate ≤ 10%
* Within that constraint, make intervals as narrow as possible

This reflects a typical business objective:

* maintain reliability guarantees
* maximize precision of the promise

## 6. Evaluation Metrics

To evaluate different policies, we use three key metrics:

### 6.1 Late Delivery Rate

- Percentage of orders delivered after the promised end time

* primary measure of reliability
* most important operational KPI

### 6.2 Interval Width

- end_time − start_time

* measures how informative the promise is
* smaller is better

### 6.3 Coverage

- Percentage of deliveries that fall within the promised interval

* measures calibration of the model + policy
* useful diagnostic metric

## 7. Primary Business KPI

The most critical KPI is:

- Late delivery rate

This metric directly affects:

* customer satisfaction
* operational cost (refunds, support)
* trust in the platform

Other metrics (interval width, coverage) are optimized subject to maintaining acceptable late rates.

## 8. Seller Preparation Timing (Important Extension)

In real marketplace systems, the platform may also control:

- When the seller is notified to start preparing the order

This introduces a second decision problem:

* early notification:

  * reduces delivery risk
  * increases idle courier time

* late notification:

  * improves efficiency
  * increases risk of delays

In this prototype:

* preparation is treated as part of total delivery time

In production:

> This could be modeled as a joint optimization problem:
>
> * when to trigger preparation
> * what promise to show the user

## 9. Key Challenges

Several challenges make this problem non-trivial:

* delivery time is stochastic and multi-stage
* important variables (e.g. seller prep time) may be unobserved
* different seller categories have very different distributions
* system must operate in real time at checkout
* trade-offs are business-driven, not purely statistical

## 10. Scope of This Prototype

This project focuses on:

* modeling delivery uncertainty using quantiles
* defining interval-based promise policies
* evaluating trade-offs between reliability and precision

It does not include:

* customer conversion modeling
* dynamic courier dispatch optimization
* real-time routing systems
* explicit modeling of seller preparation decisions

These are left as extensions for a full production system.
