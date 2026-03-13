# Mercado Libre Delivery Promise Optimization Prototype

## Overview
This repository contains a simplified prototype for delivery promise optimization. The project focuses on formal problem formulation, lead-time uncertainty modeling, delivery promise interval design, and policy trade-off evaluation.

The implementation is intentionally minimal. It concentrates on the core predictive and decision components of the challenge, while broader production system concerns are documented rather than fully implemented.

## Repository Structure
```text
mercado-envios-challenge/
├── README.md
├── pyproject.toml
├── .gitignore
├── config/
│   ├── dataset_config.yaml
│   └── model_config.yaml
├── data/
│   ├── raw/
│   └── processed/
├── docs/
│   ├── architecture.md
│   ├── assumptions.md
│   ├── problem_framing.md
│   └── prompt_log.md
├── notebooks/
│   └── eda.ipynb
└── src/
    ├── __init__.py
    ├── build_dataset.py
    ├── config_utils.py
    ├── evaluate_policy.py
    ├── train_model.py
    └── train_quantiles.py
```

## Prototype Scope
This repository implements a minimal prototype rather than a production logistics system. It is designed to study how uncertainty-aware lead-time predictions can be converted into buyer-facing promise intervals and how different promise policies trade off reliability against interval width.
