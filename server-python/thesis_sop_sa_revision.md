# Statement of the Problem — Revised

## Lead paragraph (replace in full)

This study aims to develop a Biologically-Informed Feature Engineering Framework for Early Rice Pest Outbreak Prediction and Warning in Central Luzon, Philippines, by integrating time-lagged, biologically-informed climate features, crop phenological stage, and a photograph-derived verified-observation signal into a BiLSTM temporal forecasting model to predict continuous pest population/damage indicators and derive Integrated Pest Management (IPM)-aligned risk classifications for the Brown Planthopper (BPH) and Rice Stem Borer (RSB). The framework is supported by a ResNet-50 visual component that both identifies the pest present in a digital field photograph and produces a quantitative estimate of infestation extent — hoppers-per-hill and affected-area coverage for BPH, damage percentage for RSB — which an agricultural technologist reviews, confirms, or corrects before it is recorded as a verified observation. Rather than serving only as a point of comparison against the forecast, this verified observation becomes a genuine input to the BiLSTM alongside the climate sequence, so that a recent, technologist-confirmed field reading can inform the model's forecast the same way a weather reading does. Specifically, it seeks to answer the following questions:

## Research questions (replace 1.2 and renumber what follows; 1.1, 2, 3 unchanged)

**1.** What is the predictive performance of the proposed system, evaluated in terms of:

**1.1.** The BiLSTM forecasting model, trained on a fourteen-day sequence of daily climate observations (maximum and minimum temperature, relative humidity, rainfall, vapor pressure deficit, and diurnal temperature range) together with window-level biologically-informed engineered features (Growing Degree Days, Cumulative Rainfall Factor, Humidity Persistence, Water Stress Index, and rainfall and temperature trends), crop growth stage, including its interactions with accumulated rainfall and temperature, **and the most recent technologist-verified field observation together with its age**, in forecasting pest-specific outbreak indicators for Brown Planthopper and Rice Stem Borer:

　1.1.1. Continuous forecasting performance: Root Mean Squared Error (RMSE), Mean Absolute Error (MAE), and Coefficient of Determination (R²), reported per pest in their native units, and as Normalized RMSE and Normalized MAE averaged across both pests to yield a unit-independent system-wide figure; and

　1.1.2. Downstream classification agreement, obtained by mapping the model's forecasted continuous output to Low, Medium, and High risk levels using pest-specific Economic Threshold Level (ETL) values: Accuracy, Precision, Recall, and F1-score, reported per pest and pooled across both pests; and

**1.2.** The ResNet-50 visual classification component, trained on digital field photographs, in (a) identifying the presence of Brown Planthopper and Rice Stem Borer, and (b) distinguishing a photograph containing an unrecognized insect from one containing no pest at all: Accuracy, Precision, Recall, and F1-score; and

**1.3.** *(new)* The ResNet-50 visual estimation components, trained on digital field photographs, in producing a quantitative hoppers-per-hill count and an affected-area coverage estimate for Brown Planthopper, and a damage-percentage estimate for Rice Stem Borer: Root Mean Squared Error (RMSE), Mean Absolute Error (MAE), and Coefficient of Determination (R²), reported per estimation target?

**2.** What is the comparative performance of the proposed BiLSTM model trained on biologically-informed engineered climate features versus the same BiLSTM architecture trained on raw, unengineered climate variables (daily maximum and minimum temperature, relative humidity, and rainfall only) in forecasting pest-specific outbreak indicators for Brown Planthopper and Rice Stem Borer, evaluated in terms of: 2.1. Continuous forecasting performance (RMSE, MAE, and R²); and 2.2. Downstream classification agreement with IPM decision levels (Accuracy, Precision, Recall, and F1-score)?

**3.** Is there a significant difference between the continuous forecasting performance and the downstream IPM classification agreement of the BiLSTM model trained on biologically-informed engineered climate features and the same model trained on raw climate variables, for Brown Planthopper and Rice Stem Borer?

**4.** *(revised to add the verified-observation feature)* Which input features, as identified through the model's explainability (SHAP-based) module, contribute most significantly to its outbreak predictions for Brown Planthopper and Rice Stem Borer, distinguishing the contribution of crop growth stage, the engineered climate features, **and the verified-observation feature**, and how consistent are these attributions with established biologically-informed climate-pest relationships?

---

# System Architecture — Revised

Only the bullets below change; everything else in the section (the five-layer framing, Figure 11/12 references, the GDD/CRF/HP formulas, Table 3's ETL values, the three-tier Software Component Architecture) is untouched — the opening paragraph's claim that "observations confirmed by an agricultural technologist are returned to the preparation layer, where they become lagged input features for subsequent forecasts" was already written this way and is, with this revision, now actually true of the deployed system rather than a design intention.

## Layer 3: Field Observation and Verification (replace these two bullets)

● **Visual Pest Identification and Quantitative Estimation:** Two ResNet-50 binary classifiers, one per pest, score the submitted photograph and report which target pest, if any, is present with its confidence, together with a separate classifier that distinguishes an unrecognized insect from no pest at all. Larger Brown Planthopper photos are divided into a grid of tiles that are scored individually. When a tracked pest is identified, a corresponding ResNet-50 regression model produces a quantitative estimate from the same photograph: hoppers-per-hill and affected-area coverage percentage for Brown Planthopper, or damage percentage for Rice Stem Borer. These estimates are suggestions for the reviewing technologist, not final values — manual submissions bypass identification and estimation entirely and proceed directly to review.

● **Detailed Field Report:** The submission, the AI-identified pest and its suggested count/coverage/damage estimate (when a photo produced one), the farmer-entered value, the municipality, and the date are assembled into a single report and presented in the administrative web application.

● **Human Verification:** An agricultural technologist reviews the report — including the AI-suggested estimate, where available — and confirms or corrects the value actually recorded. This step remains the trust gate: an AI-produced estimate assists the technologist's judgment but never becomes a verified value without that confirmation.

(Verified Observation Store bullet is unchanged.)

## Layer 4: Temporal Forecasting Model (replace this bullet)

● **Sequence and Static Inputs:** The per-day sequence for the 14-day window (maximum and minimum temperature, relative humidity, rainfall, daily vapor pressure deficit, daily diurnal temperature range, and the one-hot encoded growth stage), and a static vector containing the accumulated indices (GDD, CRF, HP, WSI), the rainfall and temperature trends, the growth-stage interaction terms, **and the municipality's most recent verified observation together with its age in days and a binary flag for whether one exists within the trained recency window** — absent when no recent verified observation exists, so the model still forecasts from climate alone in that case.

---

## Why each change was made (for your own defense prep, not for the thesis text)

- **1.3 is new** because the system now has a real, trained, evaluated regression component (RMSE/MAE/R²) that didn't exist in any earlier version of this chapter — it needs its own question or it has no evaluation home in the Statement of the Problem.
- **1.1's wording and Layer 4's bullet** both needed the verified-observation feature added explicitly, because Sources of Data (page 58) already described it ("...supply lagged observation features...which allow the model to condition its forecast on known field conditions") while System Architecture's own Layer 4 bullet never listed it — an internal inconsistency that existed before this round of changes and is now fixed because the feature is real.
- **RQ4** needed the same addition for the same reason: SHAP now genuinely attributes to this feature (`app/models/bilstm_model.py` + `ml/explainability/shap_report.py`), so the research question should say so.
- **Layer 3's bullets** are the direct description of the new CV-estimate-as-suggestion flow — written to preserve the existing "trust gate" language exactly, since that principle didn't change, only what the technologist now has in front of them when exercising it.

---

# Response to the 2026-10-consultation panel feedback (new section, added 2026-10-21)

Everything above this line predates the panel's consultation and should be read as already in progress when these comments were raised. This section answers the comments directly, point by point, against what the system actually does today — not what it's planned to do.

## "Baka may algo na kaya nya na isahang compute lang, baseline din" — the panel is right, and it's been tested

This is the panel questioning whether the baseline BiLSTM could already do what the hand-computed features (GDD/CRF/HP/WSI/trends) do, making the "framework" nothing more than extra arithmetic bolted onto an unchanged model. A controlled test now exists for exactly this: `ml/bilstm/compare_seq_only.py`, which trains the BiLSTM on raw daily climate **plus growth stage** (so phenology — SHAP's single strongest predictor, ~45% of attribution — isn't lost along with the engineered math, which would have confounded the two) against the fully engineered model.

**Result: no statistically significant difference on any of 7 metrics, for either pest** (`ml/weights/{bph,rsb}/bilstm_{pest}_seq_only_comparison.json`). RSB's seq_only configuration actually scores numerically better on 4 of 7 metrics. This directly confirms the panel's suspicion for the climate math specifically: the BiLSTM does not need the hand-computed aggregates to reach the same forecasting performance, once it has the same raw information.

**This changes what the study's contribution should be claimed as.** Do not defend the engineered formulas as what improves forecasting — the data says they don't, measurably. The defensible claim is narrower and still real:
1. The engineered features are **interpretable, named, biologically-grounded quantities** (GDD, VPD, WSI are established agrometeorological constructs) that a reader or field agronomist can audit, unlike an opaque internal LSTM representation — an explainability argument, not an accuracy argument.
2. The actual computational contribution is the **multimodal integration**: BiLSTM forecasting + ResNet-50 identification + the new ResNet-50 regression heads + the verified-observation feedback loop, assembled into one system that the prior BiLSTM-only study did not have — not the formulas inside any one component.
3. Growth stage, not the engineered climate math, is empirically the dominant driver (SHAP: 41.5%/49.0% of attribution vs. 22.3%/13.1% for all engineered climate indices combined, BPH/RSB respectively) — this is the real finding Q4 should lead with.

## "Hindi general problem ang pag-identify ng pests... dapat ma-identify, gaano kalawak, at ung risk/damage" — partially already built

The panel wants the CV component to go beyond species identification to quantitative severity/extent estimation feeding the forecast. The ResNet-50 regression heads (count, coverage %, damage %) already do this and are wired into the live photo-inference endpoint and the forecast's lagged-observation input via technologist verification (see Layer 3/4 above).

**What must be disclosed, not defended:** only the `count` target has real ground truth (`ml/resnet/bph/_annotations.csv`). `coverage_pct` and `damage_pct` are trained **entirely on synthetic composites** — real pest crops pasted onto real backgrounds at known positions for coverage, and painted tint patches *approximating* dead-heart/white-ear symptoms for RSB damage, because no real damaged-plant photographs exist anywhere in the dataset (`ml/synthetic/generate_coverage_dataset.py`). The val/test splits for those two targets are synthetic too. If asked how this generalizes to a real field photo, the honest answer is: unverified — this is a controlled proof-of-concept for the regression approach, not a validated real-world estimator, and that limitation should be stated in Chapter 5, not discovered by a panelist.

## "Field photo, not close-up; drone imagery; hectares" — not addressed, scope this as future work

The entire CV pipeline (classification and the new regression heads) is trained on close, farmer-submitted crops of individual insects, not whole-field or drone imagery. Reaching what the panel describes needs new data collection (drone or wide-field photography), new annotation at field scale, and likely a different CV approach (tiling + aggregation or true object detection) — not a retrain of what exists. **Recommendation: state this explicitly as acknowledged future work in Chapter 5** rather than attempting a redesign before the defense. Trying to partially address it risks a worse outcome than naming it plainly as out of scope.

## "PAGASA... real data" — already using real data, different source

Weather is sourced from Open-Meteo (`app/routers/weather.py`), which aggregates real observational and reanalysis data, not PAGASA directly and not synthetic. If a panelist specifically expects PAGASA by name: PAGASA's own API was not available to the team as students; Open-Meteo was used as a real-data substitute covering the Philippines. State this as a one-line clarification, not a defense — the substance of "real weather data" is already satisfied.

## "Computational efficiency — time, memory" — was missing, now measured

No benchmark of this kind existed anywhere in the repository before this section was written. `ml/bilstm/benchmark_efficiency.py` now measures training wall-clock time, per-request inference latency, and peak memory footprint for the baseline (raw), the deployed (engineered), and the seq_only configurations, per pest, each run in its own process so the memory figure isn't carried over between configurations. Single run per configuration (not the 5-fold CV the significance tests use — efficiency doesn't need paired folds the way a significance test does), same architecture, same 60-epoch cap with early stopping, same hardware, one after another.

| Pest | Config | Train time | Epochs | Inference (mean / p95) | Peak memory | R² |
|---|---|---|---|---|---|---|
| BPH | raw (baseline) | 42.1 s | 28 | 32.3 / 34.8 ms | 405.8 MB | 0.178 |
| BPH | engineered (deployed) | 34.1 s | 21 | 37.9 / 46.5 ms | 426.4 MB | 0.312 |
| BPH | seq_only | 31.1 s | 20 | 32.5 ms | 417.1 MB | 0.341 |
| RSB | raw (baseline) | 31.0 s | 20 | 32.6 ms | 405.4 MB | 0.009 |
| RSB | engineered (deployed) | 38.9 s | 25 | 35.4 ms | 427.5 MB | 0.178 |
| RSB | seq_only | 32.7 s | 21 | 45.2 ms | 416.7 MB | 0.196 |

**Reading this honestly, including the parts that don't flatter the engineered configuration:**

- **Memory cost of the engineered features is small and real**: ~20 MB more than raw for both pests (≈5%), from the 9 extra static features and their Dense(8) branch. Not expensive, but not free either — don't claim "no computational cost."
- **Training time does not favor engineered in a straight line.** BPH: engineered trains faster than raw (34.1s vs 42.1s) because early stopping triggered sooner — fewer epochs, not a faster epoch. RSB: engineered is the *slowest* of the three (38.9s). Epoch count is driven by when validation loss stops improving, which varies run to run on a model this size; this one comparison is not a stable efficiency ranking across repeated runs, and should be described as such rather than as "engineered is faster."
- **Inference latency is in the same ballpark for all three** (32–46ms per request, one window at a time, no batching) — the static branch's few extra parameters don't move single-request latency in any direction a user would notice. This is the cleanest efficiency claim available: engineered features cost essentially nothing in serving latency.
- **seq_only is the most memory- and parameter-efficient of the three on BPH, and ties for cheapest on RSB, while matching or beating engineered on R² for both pests** — consistent with the significance-test result above. If efficiency is weighed alongside accuracy, seq_only is arguably the strongest configuration of the three, not the engineered one. This should be said plainly if asked, not avoided.

**What this does NOT establish**: a single run per configuration has run-to-run noise (weight initialization, early-stopping timing) that these numbers don't quantify — this is a defensible first measurement answering "did you check," not a rigorously replicated efficiency study. If more rigor is wanted before the defense, each configuration should be repeated several times and reported as mean ± std; that was out of scope for closing the panel's immediate gap.
