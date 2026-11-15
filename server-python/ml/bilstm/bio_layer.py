"""A small learnable layer that gives the BiLSTM a biological way to look at each day.

No formula is hardcoded. Every number below is a trainable weight that the model sets
from the data, starting from random values. What is fixed is only the SHAPE of each
question, taken from how these pests respond to weather:

  - heat gate:   is this day warmer than some base temperature? (a learned mix of Tmax
                 and Tmin, minus a learned threshold, floored at zero)
  - humid gate:  is humidity above some level? (a smooth yes/no with a learned level
                 and a learned sharpness)
  - dry gate:    how far does rainfall fall short of some level? (learned level)
  - wet gate:    is rainfall above some level? (smooth yes/no, learned level)

Each kind has `n_gates` copies, so the model can keep more than one threshold. The gates
are appended to the day's raw inputs, and the BiLSTM then accumulates them over the 14
days by itself (accumulated heat, run of humid days, water deficit, ...). The learned
thresholds can be read back in real units with `learned_thresholds()` to see what the
model found, for example the temperature above which it starts counting heat.

Input convention: the first four columns of the sequence are the scaled Tmax, Tmin,
relative humidity and rainfall (the order build_sequences.py writes them in).
"""

import numpy as np
from tensorflow import keras
from tensorflow.keras import ops


@keras.utils.register_keras_serializable(package="pestwatcher")
class LearnedBiologyGates(keras.layers.Layer):
    def __init__(self, n_gates: int = 2, **kwargs):
        super().__init__(**kwargs)
        self.n_gates = n_gates

    def build(self, input_shape):
        g = self.n_gates
        rnd = keras.initializers.RandomNormal(stddev=0.5)
        zero = keras.initializers.Zeros()
        self.heat_w = self.add_weight(name="heat_w", shape=(2, g), initializer=rnd)
        self.heat_t = self.add_weight(name="heat_t", shape=(g,), initializer=rnd)
        self.humid_t = self.add_weight(name="humid_t", shape=(g,), initializer=rnd)
        self.humid_k = self.add_weight(name="humid_k", shape=(g,), initializer=zero)
        self.dry_t = self.add_weight(name="dry_t", shape=(g,), initializer=rnd)
        self.wet_t = self.add_weight(name="wet_t", shape=(g,), initializer=rnd)
        self.wet_k = self.add_weight(name="wet_k", shape=(g,), initializer=zero)
        super().build(input_shape)

    def call(self, x):
        tmax, tmin, rh, rain = x[..., 0:1], x[..., 1:2], x[..., 2:3], x[..., 3:4]
        heat = ops.relu(tmax * self.heat_w[0] + tmin * self.heat_w[1] - self.heat_t)
        humid = ops.sigmoid(ops.softplus(self.humid_k) * 3.0 * (rh - self.humid_t))
        dry = ops.relu(self.dry_t - rain)
        wet = ops.sigmoid(ops.softplus(self.wet_k) * 3.0 * (rain - self.wet_t))
        return ops.concatenate([x, heat, humid, dry, wet], axis=-1)

    def compute_output_shape(self, input_shape):
        return (*input_shape[:-1], input_shape[-1] + 4 * self.n_gates)

    def get_config(self):
        return {**super().get_config(), "n_gates": self.n_gates}

    def learned_thresholds(self, mean: np.ndarray, scale: np.ndarray) -> dict:
        """The learned thresholds converted back to real units, given the StandardScaler's
        per-column mean and scale for (Tmax, Tmin, RH, Rainfall)."""
        hw = np.array(self.heat_w)
        ht = np.array(self.heat_t)
        # temperature T at which a day with Tmax = Tmin = T starts to count as heat
        slope = hw[0] / scale[0] + hw[1] / scale[1]
        offset = hw[0] * mean[0] / scale[0] + hw[1] * mean[1] / scale[1]
        base_temp = (ht + offset) / np.where(np.abs(slope) < 1e-6, 1e-6, slope)
        return {
            "heat_base_temperature_c": base_temp.tolist(),
            "heat_weight_tmax_vs_tmin": (hw[0] / (np.abs(hw).sum(axis=0) + 1e-9)).tolist(),
            "humid_level_pct": (np.array(self.humid_t) * scale[2] + mean[2]).tolist(),
            "humid_sharpness": (np.log1p(np.exp(np.array(self.humid_k)))).tolist(),
            "dry_rainfall_level_mm": (np.array(self.dry_t) * scale[3] + mean[3]).tolist(),
            "wet_rainfall_level_mm": (np.array(self.wet_t) * scale[3] + mean[3]).tolist(),
        }
