"""Placeholder entry point for baseline point-model training."""

from src.config_utils import load_config


def main() -> None:
    """Run the Stage 1 placeholder for point-model training."""
    model_config = load_config("config/model_config.yaml")

    # TODO: Load the processed training dataset.
    # TODO: Split features and target for lead_time_minutes prediction.
    # TODO: Train a LightGBMRegressor using the configured parameters.
    # TODO: Persist the fitted baseline model and training metadata.
    print("Running train_model.py - Stage 1 placeholder")
    print("Model training not implemented yet.")
    print(f"Loaded model configuration keys: {sorted(model_config.keys())}")


if __name__ == "__main__":
    main()
