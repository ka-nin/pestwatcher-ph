> **SUPERSEDED (24 October 2026).** This draft describes the earlier framework with hand-computed formulas (GDD, CRF, HP, VPD, WSI). The panel asked for no hardcoded formulas, and the framework now reads raw weather, growth stage and the verified observation. The current wording is in the Thesis Text Updates document, and the evidence is in the Panel Concerns Technical Report. Do not paste text from below without checking it against those.

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

> **Update 2026-10-21 (later):** the deployed BiLSTM was retrained as `lagged_fresh` (half the training windows have no report, the rest one aged 0 to 30 days), and the dataset is confirmed to be adviser-approved augmentation of the agency datasets. The reconstructed SOP with current results is in `PestWatcherPH_SOP_Reconstructed.pdf`; where its numbers differ from the sections below, the PDF is current. The earlier `lagged` framework comparison is kept as `bilstm_{pest}_framework_comparison_lagged.json`.


> **Read this first: the BiLSTM's historical dataset is synthetic augmentation of the agency datasets, as advised.** Confirmed 2026-10-21: `ml/datasets/raw/{weather,pest}_raw.csv` (and so `weather_pest_daily_clean.csv`, all 10,960 rows) come from a synthetic generator, and the weather is synthetic too, not only the pest values. Compared with the real Open-Meteo archive for Arayat over March–April 2023, the CSV's Tmax correlates at −0.23 and its rainfall at 0.05 with what actually happened. Every BiLSTM number in this document (test metrics, the 5-fold comparisons, `seq_only`, the framework comparison, SHAP, the scatter plots) therefore describes **the generator's structure, not real rice-pest behaviour**. See "The synthetic dataset" below before quoting any of them.

Everything above this line predates the panel's consultation and should be read as already in progress when these comments were raised. This section answers the comments directly, point by point, against what the system actually does today — not what it's planned to do.

## "Baka may algo na kaya nya na isahang compute lang, baseline din" — the panel is right, and it's been tested

This is the panel questioning whether the baseline BiLSTM could already do what the hand-computed features (GDD/CRF/HP/WSI/trends) do, making the "framework" nothing more than extra arithmetic bolted onto an unchanged model. A controlled test now exists for exactly this: `ml/bilstm/compare_seq_only.py`, which trains the BiLSTM on raw daily climate **plus growth stage** (so phenology — SHAP's single strongest predictor, 42–50% of attribution — isn't lost along with the engineered math, which would have confounded the two) against the fully engineered model.

**Result: no statistically significant difference on any of 7 metrics, for either pest** (`ml/weights/{bph,rsb}/bilstm_{pest}_seq_only_comparison.json`). RSB's seq_only configuration actually scores numerically better on 4 of 7 metrics. This directly confirms the panel's suspicion for the climate math specifically: the BiLSTM does not need the hand-computed aggregates to reach the same forecasting performance, once it has the same raw information.

**This changes what the study's contribution should be claimed as.** Do not defend the engineered formulas as what improves forecasting — the data says they don't, measurably. The defensible claim is narrower and still real:
1. The engineered features are **interpretable, named, biologically-grounded quantities** (GDD, VPD, WSI are established agrometeorological constructs) that a reader or field agronomist can audit, unlike an opaque internal LSTM representation — an explainability argument, not an accuracy argument.
2. The framework as a whole **does** significantly beat the panel's baseline on forecasting error (see the framework comparison section below), and the evidence attributes that gain to **giving the model crop phenology**, not to the formulas and not (yet) to the verified observation. That's the accurate claim for what the framework adds over the previous BiLSTM-only study.
3. Growth stage, not the engineered climate math, is empirically the dominant driver. SHAP on the deployed model attributes 42.2% (BPH) and 49.5% (RSB) of the model's output to growth stage, against 9.7% and 16.3% for all engineered climate indices combined, and 6.4% and 2.7% for the verified observation. This is the real finding Q4 should lead with.
4. The system's other real addition is **structural**: it turns a photo into a quantitative, technologist-verified observation that the forecaster can consume. That pipeline exists and runs. Its measured forecasting benefit is not significant yet, for the reason given in the framework comparison section, so present it as a capability built and evaluated, not as an accuracy gain.

## "Hindi general problem ang pag-identify ng pests... dapat ma-identify, gaano kalawak, at ung risk/damage" — partially already built

The panel wants the CV component to go beyond species identification to quantitative severity/extent estimation feeding the forecast. The ResNet-50 regression heads (count, coverage %, damage %) already do this and are wired into the live photo-inference endpoint and the forecast's lagged-observation input via technologist verification (see Layer 3/4 above).

**What must be disclosed, not defended:** only the `count` target has real ground truth (`ml/resnet/bph/_annotations.csv`). `coverage_pct` and `damage_pct` are trained **entirely on synthetic composites** — real pest crops pasted onto real backgrounds at known positions for coverage, and painted tint patches *approximating* dead-heart/white-ear symptoms for RSB damage, because no real damaged-plant photographs exist anywhere in the dataset (`ml/synthetic/generate_coverage_dataset.py`). The val/test splits for those two targets are synthetic too. If asked how this generalizes to a real field photo, the honest answer is: unverified — this is a controlled proof-of-concept for the regression approach, not a validated real-world estimator, and that limitation should be stated in Chapter 5, not discovered by a panelist.

## "Field photo, not close-up; drone imagery; hectares" — partly addressed (updated 2026-10-23)

**What was built.** A field-level damage model for RSB (ResNet-50 on a 3×3 grid of cells, `ml/resnet/train_field_damage.py`) reports severity (share of the photo covered by damage) and spread (share of cells with damage). The scan flow is: the BPH classifier counts planthoppers and feeds the forecast; if no pest is found, the photo is checked for stem-borer damage, and a flagged photo is reported as an RSB case with severity, spread and a 13-day trajectory. The pest type is filled in automatically from the photo in the scan, the admin Field Assessment page and the report form. BPH has no field-level model because no field-level BPH dataset exists.

**How well it works on real photos (2026-10-23).** The model was trained on synthetic damage painted onto real healthy photos, so it was tested on the public "Symptom-Labeled Image Dataset of Rice Plants for Stem Borer Infestation Classification" (Mendeley, CC BY 4.0; real, expert-labelled phone photos from Bangladesh), 100 random photos per class:

| Class | Flagged as RSB damage |
|---|---|
| White Head | 89% |
| Dead Heart | 99% |
| Healthy | 12% (false alarm) |

This supports using it as a damage *screen* on real photos. It does **not** validate the severity percentage, the spread or any area: the dataset has class labels, not measured damage percentages. These photos are extreme close-ups of one to three stalks, not whole fields. Disclose this as a limit.

**Hectares: what a photo can and cannot give.** A photo has no scale of its own. Two sources of scale are supported:
- **Drone photos** that record their height (XMP `RelativeAltitude`) and lens: the ground footprint is computed from the lens field of view, assuming a straight-down shot. Photos without this metadata, or taken at an angle, are not given an area.
- **A field size entered by the user** (hectares or m²): affected area = severity × field size, which assumes the photo is representative of the field.

An earlier version estimated a ground-level photo's area from an assumed camera height (1.5 m) and tilt (35°). It reported about 4 m² affected for a close-up that covers a few centimetres, so it was removed from the screens. Plant spacing (about 20 × 20 cm per hill) could give scale for wide photos but not for close-ups, and was not built because there are no wide field photos to test it on. A close-up's area is not the field's area, so hectares for close-ups can only come from the entered field size.

**Recommendation for Chapter 5.** State that field-level assessment is an experimental extension: RSB only, trained on synthetic damage, screened on a public real dataset, with severity and area unvalidated until photos with technologist-measured damage and known area are collected (`ml/resnet/evaluate_real_photos.py` is ready for that).

## "PAGASA... real data" — already using real data, different source

Weather is sourced from Open-Meteo (`app/routers/weather.py`), which aggregates real observational and reanalysis data, not PAGASA directly and not synthetic. If a panelist specifically expects PAGASA by name: PAGASA's own API was not available to the team as students; Open-Meteo was used as a real-data substitute covering the Philippines. State this as a one-line clarification, not a defense — the substance of "real weather data" is already satisfied.

## "Computational efficiency — time, memory" — was missing, now measured

No benchmark of this kind existed in the repository before this section was written. `ml/bilstm/benchmark_efficiency.py` trains each configuration once, in its own process, and measures training wall-clock time, single-request inference latency, and peak memory footprint (`/usr/bin/time -l`). It was run twice on the same machine. Numbers below are from the second run (2026-10-21), which added the deployed lagged model.

| Pest | Config | Train time | Epochs | Inference | Peak memory | R² |
|---|---|---|---|---|---|---|
| BPH | raw (baseline) | 25.0 s | 31 | 17.7 ms | 407.3 MB | 0.180 |
| BPH | engineered | 32.2 s | 38 | 20.2 ms | 424.5 MB | 0.311 |
| BPH | **lagged (deployed)** | 21.9 s | 25 | 17.8 ms | 428.0 MB | 0.358 |
| BPH | seq_only | 14.3 s | 17 | 22.4 ms | 416.6 MB | 0.369 |
| RSB | raw (baseline) | 20.8 s | 21 | 18.0 ms | 405.1 MB | 0.001 |
| RSB | engineered | 21.0 s | 25 | 18.0 ms | 425.5 MB | 0.188 |
| RSB | **lagged (deployed)** | 17.3 s | 21 | 17.5 ms | 426.2 MB | 0.183 |
| RSB | seq_only | 21.5 s | 27 | 20.0 ms | 417.1 MB | 0.192 |

**Reading this honestly:**

- **Memory is the one stable, reportable cost.** Across both runs, every configuration landed within about 2 MB of its earlier figure. The proposed framework costs about **20 MB (≈5%) more than the baseline**, from its static-feature branch. That's small, real, and the number to quote.
- **Training time and inference latency are not stable enough to rank configurations.** Between the two runs, BPH engineered went from 21 to 38 epochs, and inference latency for every configuration roughly halved (about 32–45 ms down to 17–22 ms) because the machine was less loaded. Epoch count is set by when early stopping triggers, which varies run to run. Any time differences in this table are within that noise. Don't say any configuration "trains faster."
- **Serving cost is the same for all of them.** About 20 ms per single forecast request on this laptop, regardless of configuration. The framework adds no meaningful latency.
- **Answer to the panel:** the proposed framework's added computation is negligible (≈5% memory, no measurable latency), so efficiency isn't an argument against it. It isn't an argument for it either. Its case rests on the accuracy result in the comparison section below.

A rigorous efficiency study would repeat each configuration several times and report mean ± standard deviation. The two runs here are enough to show which figures are stable (memory) and which aren't (time).

## "Bakit ResNet-50? Malakas sya pero may mas malakas" — justify it, and say where it could be replaced

Nothing in the repository justified the choice before this. What the code actually does (`ml/resnet/train.py`, `ml/resnet/train_regression.py`): an ImageNet-pretrained ResNet-50 backbone at 224×224, frozen while a small dense head trains, then partially unfrozen for fine-tuning at a 1e-5 learning rate. The same backbone serves the pest classifiers, the unknown-insect detector, and the count/coverage/damage regressors. Training sets are small: roughly 5,200 images for BPH and 6,500 for RSB.

**The defensible reasons:**
- **Transfer learning on a small dataset.** A few thousand images can't train a deep network from scratch. Starting from ImageNet weights is what makes this workable, and ResNet-50 is among the most widely used, best-documented backbones for exactly this kind of fine-tuning.
- **One backbone, every visual task.** Classification and regression share the architecture and preprocessing, so the system has one image pipeline to maintain and explain instead of several.
- **The classification task is already saturated.** BPH 99.0%, RSB 99.5%, unknown-insect 98.7% held-out accuracy. A stronger backbone has almost nothing left to improve on that task.

**Decision:** ResNet-50 is kept for every visual model. It was chosen as a well-established transfer-learning backbone, one backbone and one preprocessing path serve all the models, classification is already near ceiling, and the field model reaches its scores with it. Comparing other backbones is not part of this study.

## The comparison the panel actually asked for: baseline BiLSTM vs. the proposed framework (added 2026-10-21)

The panel's revised direction (item 4) defines the comparison as a baseline BiLSTM without the feature-engineering framework or image-derived input, against the proposed framework with them. None of the earlier scripts measured that: `compare_features.py` and `compare_seq_only.py` both leave out the image-derived input on both sides. `ml/bilstm/compare_framework.py` trains all three configurations on the same 5 expanding-window folds:

- **raw**: the panel's baseline. Tmax/Tmin/RH/rainfall only.
- **engineered**: + biologically-informed features and growth stage.
- **lagged**: + the latest technologist-verified observation and its age. This is the deployed model.

**Mean over 5 folds:**

| Pest | Config | RMSE | MAE | R² | Macro F1 |
|---|---|---|---|---|---|
| BPH | raw (baseline) | 8.31 | 4.24 | −0.050 | 0.329 |
| BPH | engineered | 7.65 | 3.73 | 0.100 | 0.332 |
| BPH | **lagged (framework)** | 7.71 | 3.73 | 0.084 | 0.357 |
| RSB | raw (baseline) | 1.390 | 0.917 | −0.045 | 0.320 |
| RSB | engineered | 1.235 | 0.747 | 0.170 | 0.360 |
| RSB | **lagged (framework)** | 1.224 | 0.740 | 0.181 | 0.359 |

**Significance, framework vs. baseline (lagged vs raw):**

| Metric | BPH p | RSB p |
|---|---|---|
| RMSE | 0.056 | **0.025** ✓ |
| MAE | **0.048** ✓ | **0.0001** ✓ |
| R² | **0.048** ✓ | **0.014** ✓ |
| Accuracy / Precision / Recall / F1 | n.s. | n.s. |

**Significance, what the verified observation adds on its own (lagged vs engineered):** nothing significant on any metric for either pest (every p > 0.5).

**What this lets you say, and what it doesn't:**

1. **The framework does beat the panel's baseline on forecasting error.** That's significant on MAE and R² for both pests, and on RMSE for RSB. The baseline's mean R² is negative for both pests, meaning it does worse than predicting the average, while the framework's is positive. This is the direct answer to "did the additional components improve forecasting performance compared with the baseline": yes, on the continuous forecast.
2. **Almost all of that gain comes from growth stage plus climate, not from the image-derived observation.** Adding the verified observation on top of the engineered set is statistically indistinguishable from not adding it. Combined with the `seq_only` result (the engineered formulas add nothing once growth stage is present), the improvement over baseline is best attributed to **giving the model crop phenology**, which the baseline lacks.
3. **No configuration significantly improves risk-level classification.** Precision, recall and F1 are not significant in any comparison. The improvement lives in the continuous forecast and doesn't survive the ETL bucketing.
4. **Why the verified observation shows nothing yet:** in training it comes from the historical series thinned to a simulated ~14-day reporting cadence (`build_sequences.py`), and an observation that is often a week or two stale carries little beyond what growth stage already tells the model. Its value depends on how often real verified reports arrive, which the live system hasn't yet built up. State this as untested rather than as a failure.

**A limit of the method itself:** with 5 folds, the Wilcoxon signed-rank fallback can never reach p < 0.05. Its smallest possible two-sided p-value with 5 pairs is 0.0625. Every metric that failed Shapiro-Wilk and fell back to Wilcoxon (BPH's classification metrics here, shown as p = 0.5) was therefore untestable at α = 0.05, not "tested and not significant." If a panelist asks, that is the correct answer. The fix is more folds (10 gives Wilcoxon a minimum p of about 0.002), at roughly double the run time.

## What the scatter plots show (`ml/analysis/figures/`, added 2026-10-21)

The panel asked for scatter plots of weather against pest indicators. `ml/analysis/scatter_plots.py` plots each 14-day weather summary against the pest value 14 days later (the lag the model forecasts at), coloured by growth stage, for all 10,825 windows.

- **Weather alone is a weak predictor.** Spearman ρ between any single 14-day weather summary and the pest level 14 days later is at most 0.11 for BPH and 0.03 for RSB (`correlations.csv`). That is consistent with the raw baseline's negative R².
- **Growth stage separates pest levels strongly.** BPH 14 days ahead has a median of 4 hoppers/hill when the window ends in Tillering and 0 in Ripening. 67% of Ripening days and 72% of Seedling days have zero BPH. RSB damage is highest from Tillering, Panicle and Flowering windows and near zero at Elongation and Ripening.
- **Read the growth-stage dominance with care.** Seedling and Ripening together account for 59% of all days in the dataset, and both are mostly zero-pest. Part of what the model learns from growth stage may simply be "in-season vs. off-season." That's a legitimate signal, but it isn't the same claim as "phenology drives pest biology," so don't overstate it.
- **Answered:** the dataset is synthetic (see below), so BPH being lowest at Ripening reflects the generator's rules, not field biology. Don't defend it as an entomological finding.


## The synthetic dataset: what it means and what to do (added 2026-10-21)

The panel said directly, "were talking the real data dito... sa testing, papaaexperience ko un sa inyo." This is the study's largest exposure, larger than anything else in this document, and it has to be disclosed rather than discovered.

**What is real and what isn't:**

| Part | Real? |
|---|---|
| BiLSTM training/test data (weather + pest, 2019–2024) | **No, synthetic.** The generator script is not in the repository. |
| Weather the live system forecasts from | Yes. Real Open-Meteo data at inference time. |
| ResNet-50 classification images | Real photographs (crops). |
| ResNet-50 count regression | Real annotations; 65 real test images. |
| ResNet-50 coverage/damage regression | **No, synthetic composites** (see above). |
| Verified farmer reports | Yes. 19 verified, 15 usable for comparison. |

**What this does to the findings:**
- **Growth stage "dominating" SHAP may simply be the generator's rule being recovered.** If the generator made pest levels depend mostly on growth stage, SHAP is finding exactly what was put in. That's a valid check that SHAP works, but it says nothing about real pests.
- **The framework-vs-baseline result is a result about synthetic data.** The method (5-fold CV, paired tests) is sound. The conclusion only extends to real fields if the generator is realistic, and nothing in the repository shows that it is.
- **A model trained on synthetic weather is run on real weather.** If the generator's weather–pest relationships differ from reality, the live forecasts inherit that mismatch.

**The one real-world test, and its result.** The gap analysis now compares the deployed model with the real verified farmer reports (next section). Across the 15 usable reports, the forecast without a report gave the same risk level as the technologist in **3 of 15 (20%)**. In most of the rest the model said Medium or Low while the field was High. `ml/validity_test.py`'s field check reads INCONCLUSIVE only because it requires at least 10 reports per pest (BPH has 9, RSB 6). That check had never produced a result before 2026-10-21 because the script never loaded the model; it is fixed now.

**What to do:**
1. **Find the generator and put it in the repository**, with its rules written down: how growth stage, weather and pest values were produced. Without it, nobody can say what the synthetic data does or doesn't represent.
2. **Disclose it in Chapter 3 and Chapter 5**, plainly: the forecaster was developed and evaluated on synthetic data, and validated against real field reports only on a small set (15), where agreement was low.
3. **Reframe the BiLSTM results** as evidence that the *pipeline and evaluation method* work end to end, not as evidence about pest biology. The framework-vs-baseline comparison then shows the framework can use phenology information when it exists, which is still a legitimate methods result.
4. **If time allows, get real historical pest data.** Possible sources: regional crop protection centers (DA-RCPC), PhilRice, and BPI pest surveillance or light-trap records. Real historical weather for the same municipalities and dates can be pulled from the Open-Meteo archive (or PAGASA) immediately. Even one season of real pest data would let the model be checked against reality.
5. **Keep collecting verified reports.** With 10+ per pest, `validity_test.py` produces a real pass/fail. That is the cheapest real-world evidence available.

## Gap analysis now shows what the live system actually does (changed 2026-10-21)

Until 2026-10-21 the gap analysis drew its "report-based" line with the old fading shift (forecast + gap × weight), a mechanism the live forecast stopped using on 2026-10-20. Because that shift forced the line through the verified value on the report's date, it made every report look as if it corrected the forecast.

It now shows three things, all from the deployed model:
- **Forecast without this report.** Unchanged. This is the baseline `validity_test.py` compares with the field.
- **Forecast with this report as input.** The report is fed in as the model's verified-observation input, exactly as the live forecast does once a report is verified.
- **Verified value.** What the technologist confirmed, drawn as a separate marker, never presented as a model output.

**What it revealed, on the 15 real reports:** feeding the report in changed the forecast's risk level on **zero of 14 days in 11 of 15 cases**, and on at most 3 days in the rest. For example, a verified 40 hoppers/hill (High) against a no-report forecast of 15.4 moved the forecast only to 19.1, still Medium. In the deployed model the verified-observation input is close to inert, which matches its small SHAP share (BPH 6.4%, RSB 2.7%) and the framework comparison's "adds nothing significant." The likely cause is that during training the observation came from a simulated reporting cadence on synthetic data, so the model learned to lean on it very little.

For the defense, this is the honest and complete answer to "does a verified report actually change the forecast?" The system is built so that it can, the input is wired and running, and with the current training it barely does. Retraining once real verified reports accumulate is the stated next step.
