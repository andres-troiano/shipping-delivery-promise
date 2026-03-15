# Assumptions and Simplifications

## 1. Data Assumptions
The prototype assumes that a public trip-duration dataset is a reasonable proxy for transport-duration variability in a last-mile delivery setting. It also assumes that synthetically generated seller-side variables can approximate relevant operational uncertainty well enough to demonstrate the modeling idea.

More broadly, the repository assumes that this hybrid proxy dataset is sufficient to illustrate delivery-promise prediction and policy trade-offs, even though it does not reflect the full complexity of a real marketplace logistics network.

## 2. Modeling Assumptions
The modeling design assumes that total lead time can be approximated as an additive combination of seller preparation time, pickup delay, and delivery duration. That decomposition is useful for building a structured prototype, even though real systems may contain interactions that are not cleanly additive.

The repository also assumes that gradient-boosted trees and quantile regression provide an adequate first method for baseline prediction and interval estimation. Static offline models are treated as sufficient for the challenge, and feature-target relationships are assumed stable enough for offline validation and test evaluation to be informative.

## 3. Policy Assumptions
The policy layer assumes that buyer-facing promises can be approximated using fixed quantile-based intervals such as `[q10, q90]` or `[q10, q95]`. It further assumes that policy quality can be discussed using operationally interpretable metrics such as late-delivery rate, interval width, coverage, and early-before-start rate.

The prototype intentionally ignores richer utility formulations such as explicit conversion elasticity, long-term trust effects, or segment-specific business value. Those could matter in production, but they are outside the scope of a lightweight challenge implementation.

## 4. Production Simplifications
The repository excludes several important production components:

* no routing or dispatch optimization
* no real-time courier allocation logic
* no online experimentation framework
* no feature store or streaming infrastructure
* no seller communication workflow
* no production monitoring dashboards
* no automated retraining orchestration

These simplifications are deliberate. The implementation focuses on the predictive and policy core rather than trying to reproduce a full logistics platform.

## 5. Risk of Assumptions
These assumptions could fail in several ways. Synthetic preparation and pickup-delay variables may not match real seller behavior or operational coordination patterns. Public urban trip-duration data may differ materially from actual marketplace delivery flows, especially if the network uses different courier behaviors, hub structures, or service areas.

Model calibration on proxy data may not transfer to production. In particular, upper quantiles that look reasonable offline may become miscalibrated when faced with real operational shocks, seller changes, or demand surges. Policy conclusions may also shift if business objectives include factors that are absent from this prototype, such as conversion sensitivity or customer frustration from overly wide windows.

Being explicit about these risks is important. The prototype is meant to demonstrate sound framing and method selection, not to claim production validity from proxy data alone.

## 6. Why These Simplifications Are Acceptable for the Challenge
These simplifications are acceptable because the goal of the challenge is to demonstrate correct problem framing, uncertainty-aware ML design, decision and policy reasoning, and architecture awareness rather than operational completeness.

The repository is intentionally scoped to show one coherent slice of the problem well. It aims to be rigorous enough to discuss trade-offs honestly, while remaining small enough to implement and review as a technical challenge submission.
