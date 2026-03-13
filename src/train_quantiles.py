"""Placeholder entry point for quantile-model training."""

from src.config_utils import load_config


def main() -> None:
    """Run the Stage 1 placeholder for quantile-model training."""
    model_config = load_config("config/model_config.yaml")
    quantiles = model_config.get("quantiles", [])

    # TODO: Load the processed dataset used for quantile model training.
    # TODO: Train one quantile model per requested quantile level.
    # TODO: Produce interval-oriented prediction outputs from trained models.
    # TODO: Persist the trained quantile models for later evaluation.
    print("Running train_quantiles.py - Stage 1 placeholder")
    print("Quantile training not implemented yet.")
    print(f"Configured quantiles: {quantiles}")


if __name__ == "__main__":
    main()
