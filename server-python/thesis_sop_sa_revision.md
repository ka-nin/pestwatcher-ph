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
