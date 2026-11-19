# Validating the photo scan with an agricultural technologist

The photo models were trained and tested on synthetic images. This procedure tests the scan on real
fields against a technologist's own reading, which is the evidence a panel or an agency will ask for.
It takes one field visit per site and about 30 to 40 photos in total.

## What to collect

At each spot in the field:

1. **Take the photo the way a farmer would:** phone held at chest height, tilted down, the crop
   filling the frame. Take the field-view photo first, then any close-up of insects.
2. **Mark the frame.** Note the 4 to 6 hills that sit inside the photo's frame (a stick or a ribbon
   works). The measurement in step 3 is taken on those hills, so the photo and the count describe
   the same plants.
3. **The technologist records what the photo shows** (`technologist_pest`): `BPH` (planthoppers or
   hopperburn), `RSB` (dead hearts or white ears) or `none` (healthy).
4. **The technologist measures the damage** on the marked hills, by the usual counting method:

   | Damage | How to measure | `measure` |
   |---|---|---|
   | Dead hearts (vegetative) | dead hearts / total tillers x 100 | `dead_hearts` |
   | White ears (reproductive) | white ears / total productive tillers x 100 | `white_ears` |
   | Hopperburn | hopperburned hills / hills counted x 100 | `hopperburn_hills` |

   Healthy spots are measured too (they read 0) and are as important as damaged ones: they show
   whether the scan raises false alarms.

## How many

| Kind of spot | Photos |
|---|---|
| Hopperburn | at least 8 |
| Stem-borer damage (dead hearts or white ears) | at least 8 |
| Planthoppers visible (close-up) | at least 8 |
| Healthy, at the same growth stages | at least 10 |

Fewer than 20 photos for a pest is reported but marked as too few to conclude from.

## Recording

One row per photo in `measurements.csv`, next to the photos:

```csv
photo,technologist_pest,measured_pct,measure
spot_01.jpg,BPH,25,hopperburn_hills
spot_02.jpg,RSB,6.5,white_ears
spot_03.jpg,none,0,white_ears
spot_04_closeup.jpg,BPH,,
```

Leave `measured_pct` empty when only the pest was identified (insect close-ups).

## Scoring

From `server-python/`, with the database running:

```
PYTHONPATH=. .venv/bin/python -m ml.resnet.evaluate_real_photos path/to/measurements.csv
```

It sends every photo through the same scan the app uses and writes `real_photo_evaluation.json`:

- **Pest call:** how often the app named the same pest as the technologist, and what it called each
  pest instead (for example, hopperburn reported as stem borer).
- **Damage agreement:** whether the app's severity rises and falls with the technologist's
  measurement. The app measures the share of the photo that is damaged and the technologist a share
  of tillers or hills, so these are different quantities: agreement (Spearman's rho, Pearson's r)
  is the test, not equal numbers. The MAE is shown next to a "predict the average" baseline.

## What to do with the result

- Report the pest-call accuracy and the damage agreement as the real-world result, with the number
  of photos.
- If the agreement is strong, the damage rules in `server-python/app/routers/inference.py`
  (`DAMAGE_RULES`, including the BPH rule marked as untuned) can be set from these photos instead
  of synthetic ones. Use part of the photos to set them and the rest to check them.
- If it is weak, say so: the photo severity is then a visual aid for the technologist, not a
  measurement.
