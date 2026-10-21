# Datasets: provenance

Where the data the BiLSTM is trained on comes from, and what is and isn't real.
Fill in the sections marked **TO FILL** — the panel asked for real data, and
the answer is only convincing if it can name its sources.

## Historical training data (BiLSTM)

| File | Rows | Coverage |
|---|---|---|
| `raw/weather_raw.csv` | 10,960 (+21 duplicates, removed in cleaning) | 5 Central Luzon municipalities, 2019-01-01 to 2024-12-31, daily |
| `raw/pest_raw.csv` | 10,960 (+21 duplicates) | same |
| `processed/weather_pest_daily_clean.csv` | 10,960 | merged and cleaned by `cleaning/clean_timeseries.py` |

**What it is.** A synthetic dataset generated from real datasets the team
obtained from agencies. The real records alone were too few to train a deep
model, so, on the adviser's advice, they were extended synthetically to a
trainable size. Both the weather and the pest columns are synthetic: checked
against the real Open-Meteo archive for Arayat (March to April 2023), the
CSV's daily Tmax correlates at −0.23 and rainfall at 0.05 with what actually
happened, while the value ranges are realistic.

**What that means for results.** Every BiLSTM metric, comparison and SHAP
ranking describes this dataset. Present them as results on the augmented
dataset, not as findings about real pest behaviour.

**Cleaning.** `processed/cleaning_report.json` counts every correction
(duplicates, impossible readings, interpolated gaps). The round numbers there
(21 duplicates per file, 18 of each error type) are consistent with errors
injected by the generator to make cleaning testable.

### TO FILL

- **Source datasets** (agency, dataset name, years, municipalities, variables, how obtained):
  - DOST-PAGASA CLSU station: …
  - BPI-CPMD: …
- **Generator**: where the script lives, who wrote it, and the rules it uses
  (how weather is generated, how pest values depend on weather and growth
  stage, how growth stage is scheduled). Commit the script next to this file.
- **Adviser approval**: date and who approved using augmented data.

## Live data (what the running system uses)

- **Weather**: Open-Meteo forecast and archive APIs, real observational and
  reanalysis data (`app/routers/weather.py`).
- **Field observations**: technologist-verified farmer reports in the database.
  These are the only real pest observations the system has; `ml/validity_test.py`
  compares forecasts against them.

## Image data (ResNet-50)

- **Classifiers**: real close-up photographs of insects (`ml/resnet/`, not in
  the repository; see `.gitignore`).
- **Count regressor**: real annotated BPH photos (`ml/resnet/bph/_annotations.csv`)
  plus synthetic composites; tested on 65 real photos.
- **Coverage and damage regressors**: trained and tested on synthetic composites
  only (`ml/synthetic/generate_coverage_dataset.py`): 5×5 mosaics of real
  close-up crops with pasted insects (BPH) or painted damage (RSB). These are
  not field or drone images, and accuracy on real photos is untested.
