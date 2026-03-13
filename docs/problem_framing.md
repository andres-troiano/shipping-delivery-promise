# Problem Framing

## 1. Business Context
In a marketplace logistics platform, the buyer is shown a delivery promise interval such as "Delivery today between 16:00 and 20:00." That promise is a core part of the product experience because it influences buyer trust, affects conversion, and sets a clear expectation for when the order should arrive.

The platform must issue that promise before the delivery is completed, which means the promise is made under uncertainty. A narrow promise window is more attractive to buyers because it feels precise and convenient. A wide promise window is safer operationally because it reduces the chance that the delivery arrives after the promised end time.

The promise is computed once during checkout and is not updated later during the delivery process, which means the system must commit to a promise before the operational outcome is fully known.

For that reason, the real business problem is not simply to predict delivery time. The problem is to choose a buyer-facing promise interval under uncertainty in a way that balances customer experience against operational reliability.

## 2. Problem Statement
For each order, the system must estimate uncertainty in delivery lead time and transform that uncertainty into a promise interval shown to the buyer. The promise should balance reliability, by reducing late deliveries, with customer experience, by avoiding unnecessarily wide windows.

This is therefore a decision problem informed by prediction rather than only a regression problem. Prediction estimates what is likely to happen. Policy determines what should be promised to the buyer given that uncertainty.

## 3. Why This Problem Is Hard
Delivery lead time depends on several uncertain processes that vary across orders and operating conditions. Seller preparation time may differ meaningfully between sellers and even between orders from the same seller. Pickup delays may change with courier availability or local congestion. Travel times vary with geography, route structure, traffic conditions, and time of day.

Additional variability comes from order complexity, day-of-week patterns, and local demand surges. These factors interact in nonlinear ways, and their impact is not constant across the distribution. Some orders may be easy to predict on average but still have substantial tail risk.

Because of that, a single point estimate is not sufficient on its own. The system needs an uncertainty-aware view of lead time so it can choose a promise interval with an explicit reliability trade-off.

In addition, some operational events may not be directly observable in the available data (for example intermediate preparation milestones inside the seller workflow), which introduces additional uncertainty into the modeling process.

## 4. Formal Problem Formulation
Let:

```text
T_i = total lead time for order i
X_i = feature vector for order i
```

For the prototype, total lead time is decomposed as:

```text
T_i = prep_time_i + pickup_delay_i + delivery_duration_i
```

The predictive objective is to estimate the conditional distribution:

```text
P(T_i | X_i)
```

or, in practice, to estimate useful summaries of that distribution such as its mean or selected quantiles. Those summaries can then be used to construct delivery promise intervals for each order.

## 5. Predictive Component vs Decision Component
This prototype separates the problem into two linked but distinct components.

### Predictive component
The predictive component estimates delivery lead time uncertainty conditional on the available order features. Its outputs may include a point estimate, a median, an upper quantile, or interval bounds derived from multiple quantiles.

The purpose of this layer is descriptive and probabilistic: given the order context, what outcomes are plausible, and how concentrated or dispersed is the lead time distribution?

### Decision component
The decision component converts predictive uncertainty into the buyer-facing promise shown in the product. For example, a policy may define:

* lower bound = q50
* upper bound = q90

Under this policy, the promise interval is anchored around the median expected outcome and extended to a relatively conservative upper bound. If the business instead used `q50` to `q85`, the window would usually be narrower but the late-delivery risk would be higher. If it used `q50` to `q95`, the window would usually be wider but safer.

Using quantiles in this way allows the platform to control reliability explicitly. For example, choosing the 90th percentile as the promise end time implies that roughly 90% of deliveries are expected to arrive before the promised deadline under stable conditions.

This distinction is central to the repository:

* prediction estimates uncertainty
* policy chooses how conservative the promise should be

## 6. Why Machine Learning Is Appropriate
A fixed-rule system or simple heuristic can be a useful baseline, but it is unlikely to capture the full structure of the problem. Lead time depends on many interacting factors, including seller behavior, geography, timing, and operational load. These relationships are nonlinear and can vary across sellers, regions, and time periods.

In addition, uncertainty is heteroscedastic: some orders are inherently more predictable than others. A model that can learn both central tendency and distributional differences across contexts is better suited to this setting than a one-size-fits-all rule.

That said, the prototype does not assume that machine learning replaces all heuristics. Simple heuristics remain useful as baselines, sanity checks, and fallback policies.

## 7. Target Variable and Features
The main target variable for the prototype is:

```text
lead_time_minutes
```

It is constructed as:

```text
lead_time_minutes =
prep_time_minutes
+ pickup_delay_minutes
+ delivery_duration_minutes
```

At a conceptual level, the feature space includes several groups:

* seller features: characteristics related to seller reliability, operating style, and expected preparation behavior
* order features: information about the order itself, such as complexity, priority, or item category
* temporal features: time-of-day, day-of-week, and other timing signals that affect both demand and travel conditions
* geographic or trip features: origin-destination structure, distance, and local congestion proxies
* operational workload features: indicators of courier load, queueing pressure, or marketplace demand intensity

These feature groups are intended to represent the main drivers of both average lead time and uncertainty.

## 8. Evaluation Metrics
The prototype should be evaluated at both the predictive level and the decision level.

### Predictive metrics
For point prediction, standard regression metrics such as MAE and RMSE help quantify average forecast error. They are useful for benchmarking baseline performance but do not fully describe uncertainty quality.

For quantile predictions, calibration-oriented evaluation is more relevant. This includes empirical coverage analysis and related checks that compare predicted interval behavior with realized outcomes.

### Decision / business metrics
At the policy level, the most important metrics are:

* late delivery rate: the fraction of orders whose realized lead time exceeds the promised upper bound; operationally, this measures promise failures
* average promise interval width: the average size of the buyer-facing window; operationally, this measures how much uncertainty is exposed to the buyer
* empirical coverage: the fraction of realized deliveries that fall inside the promised interval; operationally, this indicates whether the promise policy is appropriately calibrated

These metrics should not be interpreted in isolation. A policy that lowers late deliveries often does so by widening the promise interval, and a narrower promise may improve customer appeal while increasing operational risk.

## 9. Central Business Trade-off
The central business trade-off is straightforward but important: narrow intervals are attractive to buyers because they are more precise, but they increase the risk of missed promises. Wide intervals are safer operationally, but they are less compelling commercially and may reduce the perceived quality of the experience.

The main purpose of the prototype is to make this trade-off visible and measurable. A useful summary visualization is a policy trade-off plot where:

* x-axis = average interval width
* y-axis = late delivery rate

Each point represents a different promise policy. This makes it possible to compare how more aggressive or more conservative policies shift the balance between buyer experience and reliability.

## 10. Assumptions and Simplifications
This repository is intentionally a minimal prototype, so several simplifying assumptions are made explicit.

* total lead time is modeled as an additive combination of preparation, pickup, and transport components
* seller-side components can be synthetically approximated for prototype purposes
* a public trip-duration dataset can serve as a proxy for the transport component
* quantile-based intervals are a reasonable first approximation to buyer-facing promise policies
* the prototype does not model the full dispatch, routing, courier assignment, or real-time logistics control system

These assumptions are not hidden limitations; they are part of the deliberate scope definition. The goal is to isolate the predictive and policy problem while remaining transparent about what is abstracted away.

## 11. Alternative Approaches
Several other approaches are relevant but are not implemented in this prototype.

* conformal prediction: attractive for producing intervals with formal finite-sample coverage guarantees under appropriate assumptions
* full probabilistic forecasting: useful when modeling the entire conditional lead-time distribution more directly
* survival analysis or time-to-event models: interesting because delivery completion can be viewed as a time-to-event process
* simulation-based operational models: valuable for representing queueing, dispatch, and logistics interactions more explicitly
* optimization-based dispatch-coupled systems: important when promise generation is tightly linked to operational decision-making and resource allocation

These alternatives are worth discussing conceptually, but they are outside the scope of the minimal implementation.

## 12. Prototype Scope
The repository scope is intentionally limited to a minimal but decision-aware version of the challenge.

### Implemented
* proxy dataset construction
* point lead-time prediction
* quantile-based interval prediction
* policy trade-off evaluation

### Not implemented
* production feature pipelines
* online serving system
* retraining orchestration
* drift monitoring
* seller notification system
* dispatch optimization

This scope should be read as deliberate rather than incomplete. The prototype focuses on the core logic needed to connect uncertainty-aware prediction to promise-setting policy.

## 13. Conclusion
This prototype frames delivery promises as a minimal decision-aware system rather than a pure regression task. It combines realistic problem framing, uncertainty-aware modeling, and explicit business policy evaluation to study how a platform can choose delivery promise intervals under uncertainty.
