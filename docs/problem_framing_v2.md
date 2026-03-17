## 1. Business Context

In a marketplace logistics platform, the buyer is presented with a delivery promise such as:

- “Delivery today between 16:00 and 20:00.”

This promise plays a central role in the product experience. It directly influences conversion by shaping user expectations at checkout, and it affects trust by setting a clear commitment about when the order will arrive. When the promise is accurate and precise, it improves perceived reliability and convenience. When it fails, it leads to dissatisfaction, support interactions, and potential compensations.

A key challenge is that this promise must be issued before the delivery occurs, under uncertainty. At the moment of checkout, the system does not know the actual delivery time, only a set of features describing the order and its context.

This creates an inherent trade-off. Narrow promise intervals are more attractive to users because they feel precise and actionable, but they increase the risk of being wrong. Wider intervals are operationally safer, but degrade the user experience by being less informative.

For this reason, the problem is not simply to predict delivery time. The core problem is to make a **decision under uncertainty**: how to construct a delivery promise that balances reliability and precision.

## 2. Problem Statement

For each order, the system observes a set of features available at checkout, such as the locations of the buyer and seller, the seller category, the time of day, and proxy variables related to distance or routing.

Let T denote the actual delivery lead time, which is unknown at prediction time, and let X denote the observed features. The goal is to output a delivery promise interval defined by a start time and an end time, which will be shown to the user.

The system must therefore implement a function that maps the observed features to a promise interval. This interval should satisfy two competing objectives: it should be reliable, in the sense that deliveries rarely occur after the promised end time, and it should be informative, in the sense that the interval is not unnecessarily wide.

## 3. Prediction and Decision Layers

This problem naturally decomposes into two distinct layers: a prediction layer and a decision layer.

The prediction layer is responsible for estimating the uncertainty in delivery time given the observed features. Instead of predicting a single point estimate, the system models the distribution of possible delivery times. In this prototype, this is done using quantile regression, which provides estimates of different percentiles of the delivery time distribution, such as the 10th, 50th, 90th, or 95th percentiles. These quantiles provide a practical way to represent uncertainty without assuming a specific parametric distribution.

The decision layer, or policy layer, takes these predicted quantiles and transforms them into a delivery promise. For example, the system may choose to use a lower quantile as the start of the interval and an upper quantile as the end. Different choices of quantiles correspond to different policies. A conservative policy will produce wider intervals with lower risk of late deliveries, while an aggressive policy will produce narrower intervals at the cost of higher risk.

This separation between prediction and decision is critical. The model is responsible for estimating uncertainty as accurately as possible, while the policy encodes the business trade-offs between reliability and user experience.

## 4. Objective and Trade-offs

The system must balance three competing factors.

First, late deliveries occur when the actual delivery time exceeds the promised end time. These events are highly undesirable because they directly impact customer satisfaction and generate operational costs such as support interactions and compensations.

Second, early deliveries occur when the order arrives before the promised start time. While less critical than late deliveries, they reduce the credibility and usefulness of the promise by making the interval less meaningful.

Third, the width of the interval determines how informative the promise is. Narrow intervals improve the user experience by providing precise expectations, while wide intervals reduce clarity and perceived quality.

Conceptually, the goal is to minimize late deliveries while keeping the interval as narrow as possible. In practice, this trade-off is often handled through constraints rather than explicit cost functions. A common approach is to enforce a maximum acceptable late delivery rate, and within that constraint, optimize for the narrowest possible intervals.

## 5. Evaluation Metrics

To evaluate the system, we consider three key metrics.

The most important metric is the late delivery rate, defined as the fraction of orders delivered after the promised end time. This is the primary operational KPI because it directly reflects reliability and customer impact.

The second metric is the average interval width, which measures how informative the promise is. Smaller widths correspond to better user experience, as they provide more precise expectations.

The third metric is coverage, defined as the fraction of deliveries that fall within the promised interval. This metric is useful for assessing whether the predicted intervals are well calibrated, although it is secondary to the late delivery rate from a business perspective.

## 6. Seller Preparation Timing

In real marketplace systems, the platform may also control when the seller is notified to begin preparing the order. This introduces an additional decision layer that interacts with the delivery promise.

Triggering preparation earlier can reduce the risk of delays, but may lead to inefficiencies such as idle courier time. Triggering it later can improve operational efficiency, but increases the risk of missing the promised window.

In this prototype, seller preparation is treated as part of the stochastic delivery time. However, in a production system, it could be modeled explicitly and jointly optimized with the delivery promise.

## 7. Key Challenges

Several factors make this problem challenging in practice. Delivery time is a stochastic process composed of multiple stages, some of which may not be directly observed, such as seller preparation time. Different seller categories exhibit very different behaviors, leading to heterogeneous distributions. The system must operate in real time at checkout, which imposes latency constraints. Finally, the trade-offs involved are driven by business considerations, not purely by predictive accuracy.

## 8. Scope of the Prototype

This prototype focuses on modeling delivery uncertainty using quantile regression, defining interval-based promise policies, and evaluating the trade-offs between reliability and precision.

It does not attempt to model customer conversion effects, dynamic courier assignment, real-time routing, or the explicit optimization of seller-side decisions. These aspects are important in production systems but are outside the scope of this simplified implementation.
