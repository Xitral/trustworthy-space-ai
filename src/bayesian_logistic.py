from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from scipy.optimize import minimize
from scipy.special import expit

from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from train_models import (
    EARLY_HORIZONS,
    evaluate_predictions,
    get_feature_columns,
    make_event_splits,
)


warnings.filterwarnings("ignore")


PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

INPUT_PATH = PROCESSED_DIR / "horizon_snapshots.parquet"

METRICS_OUTPUT_PATH = RESULTS_DIR / "bayesian_logistic_metrics.csv"
PREDICTIONS_OUTPUT_PATH = RESULTS_DIR / "bayesian_logistic_predictions.csv"

RANDOM_SEED = 42

# Gaussian prior over non-intercept weights.
# Since features are standardized, variance=10 is a weak but stabilizing prior.
PRIOR_VARIANCE = 10.0

# Give the intercept a much weaker prior so the model can learn the rare-event base rate.
INTERCEPT_PRIOR_VARIANCE = 1_000_000.0

N_POSTERIOR_SAMPLES = 500
MAX_OPTIMIZATION_ITER = 1000

# Safety limits for numerical stability in the Laplace covariance.
POSTERIOR_EIGENVALUE_MIN = 1e-12
POSTERIOR_EIGENVALUE_MAX = 100.0

EXTRA_EXCLUDE_COLUMNS = {
    "final_time_to_tca",
    "requested_horizon_days",
    "meets_requested_horizon",
    "is_horizon_fallback",
}


class LaplaceBayesianLogisticRegression:
    """
    Bayesian logistic regression with:

    - Gaussian prior over coefficients
    - Bernoulli likelihood
    - MAP estimation by numerical optimization
    - Laplace posterior approximation around the MAP estimate
    - posterior predictive samples for uncertainty

    This is a real Bayesian baseline in the lightweight classical sense:
    it defines a prior, likelihood, approximate posterior, and posterior
    predictive distribution.
    """

    def __init__(
        self,
        prior_variance: float = PRIOR_VARIANCE,
        intercept_prior_variance: float = INTERCEPT_PRIOR_VARIANCE,
        n_posterior_samples: int = N_POSTERIOR_SAMPLES,
        random_state: int = RANDOM_SEED,
        max_iter: int = MAX_OPTIMIZATION_ITER,
    ) -> None:
        self.prior_variance = prior_variance
        self.intercept_prior_variance = intercept_prior_variance
        self.n_posterior_samples = n_posterior_samples
        self.random_state = random_state
        self.max_iter = max_iter

        self.map_params_: np.ndarray | None = None
        self.posterior_covariance_: np.ndarray | None = None
        self.posterior_samples_: np.ndarray | None = None

        self.optimizer_success_: bool | None = None
        self.optimizer_message_: str | None = None
        self.optimizer_iterations_: int | None = None
        self.map_objective_: float | None = None

    @staticmethod
    def _add_intercept(x: np.ndarray) -> np.ndarray:
        intercept = np.ones((x.shape[0], 1), dtype=float)
        return np.hstack([intercept, x])

    def _prior_precision(self, n_params: int) -> np.ndarray:
        precision = np.full(n_params, 1.0 / self.prior_variance, dtype=float)
        precision[0] = 1.0 / self.intercept_prior_variance
        return precision

    def _negative_log_posterior_and_gradient(
        self,
        params: np.ndarray,
        x_with_intercept: np.ndarray,
        y: np.ndarray,
    ) -> tuple[float, np.ndarray]:
        logits = x_with_intercept @ params
        probabilities = expit(logits)

        # Bernoulli negative log likelihood:
        # sum(log(1 + exp(logit)) - y * logit)
        negative_log_likelihood = np.sum(np.logaddexp(0.0, logits) - y * logits)

        prior_precision = self._prior_precision(len(params))
        negative_log_prior = 0.5 * np.sum(prior_precision * params * params)

        objective = negative_log_likelihood + negative_log_prior

        gradient_likelihood = x_with_intercept.T @ (probabilities - y)
        gradient_prior = prior_precision * params
        gradient = gradient_likelihood + gradient_prior

        return float(objective), gradient

    def _hessian_at_map(
        self,
        x_with_intercept: np.ndarray,
        params: np.ndarray,
    ) -> np.ndarray:
        logits = x_with_intercept @ params
        probabilities = expit(logits)

        weights = probabilities * (1.0 - probabilities)
        weights = np.clip(weights, 1e-12, None)

        weighted_x = x_with_intercept * weights[:, None]

        prior_precision = self._prior_precision(len(params))
        hessian = x_with_intercept.T @ weighted_x
        hessian += np.diag(prior_precision)

        # Symmetrize to reduce tiny floating-point asymmetries.
        hessian = 0.5 * (hessian + hessian.T)

        return hessian

    @staticmethod
    def _make_psd_covariance(covariance: np.ndarray) -> np.ndarray:
        covariance = 0.5 * (covariance + covariance.T)

        eigenvalues, eigenvectors = np.linalg.eigh(covariance)

        eigenvalues = np.clip(
            eigenvalues,
            POSTERIOR_EIGENVALUE_MIN,
            POSTERIOR_EIGENVALUE_MAX,
        )

        covariance_psd = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        covariance_psd = 0.5 * (covariance_psd + covariance_psd.T)

        return covariance_psd

    def fit(self, x: np.ndarray, y: np.ndarray) -> "LaplaceBayesianLogisticRegression":
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        if len(np.unique(y)) < 2:
            raise ValueError("Bayesian logistic regression requires both classes in training data.")

        x_with_intercept = self._add_intercept(x)
        n_params = x_with_intercept.shape[1]

        initial_params = np.zeros(n_params, dtype=float)

        result = minimize(
            fun=lambda params: self._negative_log_posterior_and_gradient(
                params,
                x_with_intercept,
                y,
            ),
            x0=initial_params,
            jac=True,
            method="L-BFGS-B",
            options={
                "maxiter": self.max_iter,
                "ftol": 1e-9,
                "gtol": 1e-6,
            },
        )

        self.map_params_ = result.x.astype(float)
        self.optimizer_success_ = bool(result.success)
        self.optimizer_message_ = str(result.message)
        self.optimizer_iterations_ = int(result.nit)
        self.map_objective_ = float(result.fun)

        hessian = self._hessian_at_map(x_with_intercept, self.map_params_)

        # Add tiny jitter for numerical stability before pseudo-inversion.
        jitter = 1e-8 * np.eye(hessian.shape[0])
        covariance = np.linalg.pinv(hessian + jitter)
        covariance = self._make_psd_covariance(covariance)

        self.posterior_covariance_ = covariance

        rng = np.random.default_rng(self.random_state)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        eigenvalues = np.clip(
            eigenvalues,
            POSTERIOR_EIGENVALUE_MIN,
            POSTERIOR_EIGENVALUE_MAX,
        )

        # Sample from N(map_params, covariance) using the eigendecomposition.
        standard_normal = rng.normal(
            size=(self.n_posterior_samples, n_params),
        )
        covariance_factor = eigenvectors * np.sqrt(eigenvalues)
        self.posterior_samples_ = self.map_params_ + standard_normal @ covariance_factor.T

        return self

    def predict_map_proba(self, x: np.ndarray) -> np.ndarray:
        if self.map_params_ is None:
            raise RuntimeError("Model must be fit before prediction.")

        x_with_intercept = self._add_intercept(np.asarray(x, dtype=float))
        logits = x_with_intercept @ self.map_params_
        return expit(logits)

    def predict_posterior_proba(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.posterior_samples_ is None:
            raise RuntimeError("Model must be fit before posterior prediction.")

        x_with_intercept = self._add_intercept(np.asarray(x, dtype=float))

        logits = x_with_intercept @ self.posterior_samples_.T
        probabilities = expit(logits)

        posterior_mean = probabilities.mean(axis=1)
        posterior_std = probabilities.std(axis=1)

        return posterior_mean, posterior_std


def sanitize_features(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()

    feature_cols = [col for col in feature_cols if col not in EXTRA_EXCLUDE_COLUMNS]

    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], np.nan)

    float32_safe_max = 1e30
    df[feature_cols] = df[feature_cols].clip(
        lower=-float32_safe_max,
        upper=float32_safe_max,
        axis=1,
    )

    missing_rate = df[feature_cols].isna().mean()
    feature_cols = [col for col in feature_cols if missing_rate[col] < 0.99]

    nunique = df[feature_cols].nunique(dropna=True)
    feature_cols = [col for col in feature_cols if nunique[col] > 1]

    return df, feature_cols


def prepare_design_matrices(
    train_df: pd.DataFrame,
    split_df: pd.DataFrame,
    feature_cols: list[str],
) -> tuple[np.ndarray, np.ndarray, SimpleImputer, StandardScaler]:
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()

    x_train_imputed = imputer.fit_transform(train_df[feature_cols])
    x_train_scaled = scaler.fit_transform(x_train_imputed)

    x_split_imputed = imputer.transform(split_df[feature_cols])
    x_split_scaled = scaler.transform(x_split_imputed)

    return x_train_scaled, x_split_scaled, imputer, scaler


def transform_with_existing_preprocessor(
    split_df: pd.DataFrame,
    feature_cols: list[str],
    imputer: SimpleImputer,
    scaler: StandardScaler,
) -> np.ndarray:
    x_imputed = imputer.transform(split_df[feature_cols])
    x_scaled = scaler.transform(x_imputed)
    return x_scaled


def add_metric_row(
    rows: list[dict],
    model_name: str,
    horizon: str,
    split_name: str,
    split_df: pd.DataFrame,
    y_prob: np.ndarray,
    posterior_std: np.ndarray | None,
    model: LaplaceBayesianLogisticRegression,
) -> None:
    y = split_df["high_risk"].astype(int).to_numpy()
    metrics = evaluate_predictions(y, y_prob)

    if posterior_std is None:
        mean_posterior_std = np.nan
        median_posterior_std = np.nan
        mean_posterior_std_positive = np.nan
        mean_posterior_std_negative = np.nan
    else:
        mean_posterior_std = float(np.mean(posterior_std))
        median_posterior_std = float(np.median(posterior_std))

        mean_posterior_std_positive = (
            float(np.mean(posterior_std[y == 1])) if np.any(y == 1) else np.nan
        )

        mean_posterior_std_negative = (
            float(np.mean(posterior_std[y == 0])) if np.any(y == 0) else np.nan
        )

    rows.append(
        {
            "model": model_name,
            "horizon": horizon,
            "split": split_name,
            "n": len(split_df),
            "positive_rate": float(y.mean()),
            "prior_variance": model.prior_variance,
            "intercept_prior_variance": model.intercept_prior_variance,
            "n_posterior_samples": model.n_posterior_samples,
            "optimizer_success": model.optimizer_success_,
            "optimizer_iterations": model.optimizer_iterations_,
            "map_objective": model.map_objective_,
            "mean_posterior_std": mean_posterior_std,
            "median_posterior_std": median_posterior_std,
            "mean_posterior_std_positive": mean_posterior_std_positive,
            "mean_posterior_std_negative": mean_posterior_std_negative,
            **metrics,
        }
    )


def make_prediction_rows(
    split_df: pd.DataFrame,
    horizon: str,
    split_name: str,
    map_probability: np.ndarray,
    posterior_mean_probability: np.ndarray,
    posterior_std_probability: np.ndarray,
) -> list[dict]:
    rows = []

    y = split_df["high_risk"].astype(int).to_numpy()

    for event_id, y_true, map_prob, posterior_mean, posterior_std in zip(
        split_df["event_id"].astype(str),
        y,
        map_probability,
        posterior_mean_probability,
        posterior_std_probability,
    ):
        rows.append(
            {
                "event_id": event_id,
                "horizon": horizon,
                "split": split_name,
                "high_risk": int(y_true),
                "map_probability": float(map_prob),
                "posterior_mean_probability": float(posterior_mean),
                "posterior_std_probability": float(posterior_std),
            }
        )

    return rows


def print_feature_list(feature_cols: list[str]) -> None:
    print("Bayesian logistic feature columns:")
    for col in feature_cols:
        print(f"- {col}")


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {INPUT_PATH}. Run python src/preprocess.py first."
        )

    df = pd.read_parquet(INPUT_PATH)

    required = {"event_id", "horizon", "high_risk"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["event_id"] = df["event_id"].astype(str)
    df = df[df["horizon"].isin(EARLY_HORIZONS)].copy()
    df = df.replace([np.inf, -np.inf], np.nan)

    df = make_event_splits(df)

    feature_cols = get_feature_columns(df)
    df, feature_cols = sanitize_features(df, feature_cols)

    print_feature_list(feature_cols)

    print(f"\nRows: {len(df):,}")
    print(f"Events: {df['event_id'].nunique():,}")
    print("\nClass balance:")
    event_balance = df[["event_id", "high_risk"]].drop_duplicates()["high_risk"]
    print(event_balance.value_counts())
    print(event_balance.value_counts(normalize=True))

    metric_rows = []
    prediction_rows = []

    for horizon_index, horizon in enumerate(EARLY_HORIZONS):
        horizon_df = df[df["horizon"] == horizon].copy()

        if horizon_df.empty:
            print(f"\n=== Horizon: {horizon} ===")
            print("No rows found. Skipping.")
            continue

        train_df = horizon_df[horizon_df["split"] == "train"]
        val_df = horizon_df[horizon_df["split"] == "validation"]
        test_df = horizon_df[horizon_df["split"] == "test"]

        print(f"\n=== Horizon: {horizon} ===")
        print(f"Train rows: {len(train_df):,}")
        print(f"Validation rows: {len(val_df):,}")
        print(f"Test rows: {len(test_df):,}")

        y_train = train_df["high_risk"].astype(int).to_numpy()

        if len(np.unique(y_train)) < 2:
            print("Training split has only one class. Skipping.")
            continue

        x_train_scaled, x_val_scaled, imputer, scaler = prepare_design_matrices(
            train_df=train_df,
            split_df=val_df,
            feature_cols=feature_cols,
        )

        print("Training Laplace Bayesian logistic regression...")

        model = LaplaceBayesianLogisticRegression(
            prior_variance=PRIOR_VARIANCE,
            intercept_prior_variance=INTERCEPT_PRIOR_VARIANCE,
            n_posterior_samples=N_POSTERIOR_SAMPLES,
            random_state=RANDOM_SEED + horizon_index * 1000,
            max_iter=MAX_OPTIMIZATION_ITER,
        )

        model.fit(x_train_scaled, y_train)

        print(f"Optimizer success: {model.optimizer_success_}")
        print(f"Optimizer iterations: {model.optimizer_iterations_}")
        print(f"MAP objective: {model.map_objective_:.6f}")

        split_lookup = {
            "validation": val_df,
            "test": test_df,
        }

        for split_name, split_df in split_lookup.items():
            x_split_scaled = transform_with_existing_preprocessor(
                split_df=split_df,
                feature_cols=feature_cols,
                imputer=imputer,
                scaler=scaler,
            )

            map_probability = model.predict_map_proba(x_split_scaled)
            posterior_mean_probability, posterior_std_probability = (
                model.predict_posterior_proba(x_split_scaled)
            )

            add_metric_row(
                rows=metric_rows,
                model_name="bayesian_logistic_map",
                horizon=horizon,
                split_name=split_name,
                split_df=split_df,
                y_prob=map_probability,
                posterior_std=None,
                model=model,
            )

            add_metric_row(
                rows=metric_rows,
                model_name="bayesian_logistic_posterior_predictive",
                horizon=horizon,
                split_name=split_name,
                split_df=split_df,
                y_prob=posterior_mean_probability,
                posterior_std=posterior_std_probability,
                model=model,
            )

            prediction_rows.extend(
                make_prediction_rows(
                    split_df=split_df,
                    horizon=horizon,
                    split_name=split_name,
                    map_probability=map_probability,
                    posterior_mean_probability=posterior_mean_probability,
                    posterior_std_probability=posterior_std_probability,
                )
            )

    metrics_df = pd.DataFrame(metric_rows)
    predictions_df = pd.DataFrame(prediction_rows)

    metrics_df.to_csv(METRICS_OUTPUT_PATH, index=False)
    predictions_df.to_csv(PREDICTIONS_OUTPUT_PATH, index=False)

    print("\nWrote:")
    print(METRICS_OUTPUT_PATH)
    print(PREDICTIONS_OUTPUT_PATH)

    print("\nBayesian logistic test metrics:")
    print(
        metrics_df[metrics_df["split"] == "test"]
        .sort_values(["horizon", "model"])
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()