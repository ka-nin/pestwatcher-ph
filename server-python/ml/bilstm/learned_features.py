"""A BiLSTM that LEARNS the biologically informed features instead of being handed them.

The live model never receives a calculated feature: it gets the raw daily weather, the
growth stage and the verified observation. Inside the network, two small learned parts
produce the features the study is built on:

  daily features   (per day)   vapor pressure deficit, diurnal temperature range
  window features  (per 14 days) growing degree days, cumulative rainfall, humidity
                   persistence, water stress, rainfall trend, temperature trend

and the forecast head reads them next to the BiLSTM's own patterns.

How they are learned: during TRAINING only, each learned feature is given an answer to match
(the formula's value, computed offline from the same window by ml/ablation/hand_features.py).
That is a teacher signal. It is never an input and never runs when the system predicts, so the
deployed model contains no formula. After training the network produces the features itself
from raw weather, and how closely it reproduces them is measured on windows it never saw.

Two models share one set of layers:
  train_model  : outputs forecast + window features + daily features (used to fit)
  infer_model  : outputs the forecast only (what is saved and served)
  feature_model: outputs all three (saved beside it, for inspection and tests)
"""

import numpy as np
from tensorflow import keras
from tensorflow.keras import layers

from ml.ablation import hand_features_vectorized as vf
from ml.ablation.probe_learned_features import answer_key
from ml.config import PEST_PARAMS

WINDOW_FEATURES = ["gdd", "crf", "hp", "wsi", "rainfall_trend", "temp_trend"]
DAILY_FEATURES = ["vpd", "diurnal"]
FEATURE_LABELS = {
    "gdd": "Growing degree days",
    "crf": "Cumulative rainfall",
    "hp": "Humidity persistence",
    "wsi": "Water stress index",
    "rainfall_trend": "Rainfall trend",
    "temp_trend": "Temperature trend",
    "vpd": "Vapor pressure deficit (daily)",
    "diurnal": "Diurnal temperature range (daily)",
}


def training_answers(X_raw_sequence: np.ndarray, pest: str) -> tuple[np.ndarray, np.ndarray]:
    """The teacher signal: window answers (n, 6) and daily answers (n, days, 2), from the RAW
    readings in columns 0..3 (Tmax, Tmin, RH, rainfall). Training only."""
    key = answer_key(X_raw_sequence[:, :, :4], pest)
    window = np.stack([key[name] for name in WINDOW_FEATURES], axis=1)
    n, days, _ = X_raw_sequence.shape
    tmax, tmin, rh = (X_raw_sequence[:, :, i].reshape(-1).astype(np.float64) for i in range(3))
    daily = np.stack([vf.daily_vpd(tmax, tmin, rh), vf.daily_diurnal_range(tmax, tmin)], axis=1)
    return window.astype(np.float32), daily.reshape(n, days, 2).astype(np.float32)


def build_learned_feature_models(window_days: int, n_seq_features: int, n_static_features: int, y_mean: float, y_std: float, feature_weight: float = 1.0):
    l2 = keras.regularizers.l2(1e-3)
    sequence_input = keras.Input(shape=(window_days, n_seq_features), name="sequence_input")
    static_input = keras.Input(shape=(n_static_features,), name="static_input")

    daily_hidden = layers.Dense(16, activation="tanh", name="daily_features_hidden")(sequence_input)
    daily_features = layers.Dense(len(DAILY_FEATURES), name="daily_features")(daily_hidden)
    recurrent_in = layers.Concatenate(name="inputs_plus_daily")([sequence_input, daily_features])

    x = layers.Bidirectional(layers.LSTM(16, kernel_regularizer=l2, recurrent_dropout=0.1))(recurrent_in)
    x = layers.Dropout(0.4)(x)
    window_hidden = layers.Dense(32, activation="relu", name="window_features_hidden")(x)
    window_features = layers.Dense(len(WINDOW_FEATURES), name="window_features")(window_hidden)

    s = layers.Dense(8, activation="relu", kernel_regularizer=l2)(static_input)
    merged = layers.Concatenate()([x, window_features, s])
    merged = layers.Dense(16, activation="relu", kernel_regularizer=l2)(merged)
    merged = layers.Dropout(0.4)(merged)
    # The forecast is learned on a standardised scale, like the features, so no loss drowns the
    # others; the fixed rescaling at the end puts it back in hoppers/hill or % damage.
    prediction_z = layers.Dense(1, activation="linear", name="prediction_z")(merged)
    prediction = layers.Rescaling(scale=float(y_std), offset=float(y_mean), name="prediction")(prediction_z)

    inputs = [sequence_input, static_input]
    train_model = keras.Model(inputs, [prediction_z, window_features, daily_features])
    train_model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=5e-4),
        loss={"prediction_z": "mse", "window_features": "mse", "daily_features": "mse"},
        loss_weights={"prediction_z": 1.0, "window_features": feature_weight, "daily_features": feature_weight},
    )
    feature_model = keras.Model(inputs, [prediction, window_features, daily_features])
    infer_model = keras.Model(inputs, prediction)
    infer_model.compile(optimizer=keras.optimizers.Adam(learning_rate=5e-4), loss="mse", metrics=["mae"])
    return train_model, infer_model, feature_model


def match_report(feature_model, X_seq, X_static, window_true, daily_true, w_stats, d_stats) -> dict:
    """How closely the network's own features match the formulas, in R-squared, on given windows."""
    _, w_pred, d_pred = feature_model.predict({"sequence_input": X_seq, "static_input": X_static}, verbose=0, batch_size=512)
    w_pred = w_pred * w_stats["std"] + w_stats["mean"]
    d_pred = d_pred * d_stats["std"] + d_stats["mean"]

    def r2(true, pred):
        ss = np.sum((true - pred) ** 2)
        tot = np.sum((true - true.mean()) ** 2)
        return float(1 - ss / tot) if tot > 0 else float("nan")

    out = {FEATURE_LABELS[name]: r2(window_true[:, i], w_pred[:, i]) for i, name in enumerate(WINDOW_FEATURES)}
    out.update({FEATURE_LABELS[name]: r2(daily_true[:, :, i].ravel(), d_pred[:, :, i].ravel()) for i, name in enumerate(DAILY_FEATURES)})
    return out
