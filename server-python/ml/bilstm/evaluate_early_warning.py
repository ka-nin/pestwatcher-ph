"""Measures the "High possible" early warning (app/decision/etl_thresholds.py's high_possible)
against the central-forecast risk level, on the chronological validation and test windows, with
the deployed ensemble and band exactly as app/models/bilstm_model.py serves them.

The rule adds no tuned value: it reuses the band calibrated by build_ensemble.py (validation
windows only), so the test numbers are an honest estimate.

Run from server-python/:
    PYTHONPATH=. .venv/bin/python -m ml.bilstm.evaluate_early_warning
Output: ml/weights/{pest}/bilstm_{pest}_early_warning.json
"""

import json

import joblib
import numpy as np
from tensorflow import keras

import ml.bilstm.learned_features  # noqa: F401  registers the learned-feature layers for loading
from app.decision.etl_thresholds import PEST_THRESHOLDS
from ml.bilstm.train import chronological_split, load_dataset
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS


def evaluate(pest: str) -> dict:
    k=pest.lower(); d=PEST_PARAMS[pest].bilstm_weights_path.parent
    X,S,y,meta,_,_=load_dataset(pest,"plain_fresh")
    sp=chronological_split(meta,PEST_PARAMS[pest].crf_window_days,FORECAST_HORIZON_DAYS)
    sc=joblib.load(d/f"bilstm_{k}_scalers.joblib"); band=json.loads((d/f"bilstm_{k}_ensemble.json").read_text())
    models=[keras.models.load_model(d/f"bilstm_{k}.keras",compile=False,safe_mode=False)]+[keras.models.load_model(d/f"bilstm_{k}_plain_fresh_{t}.keras",compile=False,safe_mode=False) for t in ("e2","e3","e4","e5")]
    rep=meta["is_reproductive"].to_numpy()
    result={"pest":pest,"rule":"high_possible = top of the 80% band >= the Table 2 High threshold; risk_level unchanged","band_file":f"bilstm_{k}_ensemble.json","splits":{}}
    for split in ("val","test"):
        idx=sp[split]; n,w,f=X[idx].shape
        xs=sc["sequence_scaler"].transform(X[idx].reshape(-1,f)).reshape(n,w,f); xt=sc["static_scaler"].transform(S[idx])
        mv=np.maximum(np.stack([m.predict({"sequence_input":xs,"static_input":xt},verbose=0).flatten() for m in models]),0)
        mean=np.maximum(mv.mean(0),0); half=band["band_width_factor"]*(mv.std(0)+band["disagreement_floor"]); hi=mean+half
        hmin=np.array([PEST_THRESHOLDS[pest]["Reproductive" if r else "Vegetative"].high_min for r in rep[idx]])
        lmax=np.array([PEST_THRESHOLDS[pest]["Reproductive" if r else "Vegetative"].low_max for r in rep[idx]])
        yt=y[idx]; true_high=yt>=hmin; true_low=yt<lmax
        cur=mean>=hmin; warn=hi>=hmin
        def stats(flag):
            return {"high_caught":int((flag&true_high).sum()),"high_total":int(true_high.sum()),
                    "recall":round(float((flag&true_high).sum()/max(true_high.sum(),1)),3),
                    "flags":int(flag.sum()),"precision":round(float((flag&true_high).sum()/max(flag.sum(),1)),3),
                    "flagged_truly_low":int((flag&true_low).sum()),"low_total":int(true_low.sum()),
                    "false_alarm_on_low":round(float((flag&true_low).sum()/max(true_low.sum(),1)),3)}
        result["splits"][split]={"windows":int(n),"current_high":stats(cur),"high_possible":stats(warn),
                          "band_coverage":round(float(((yt>=mean-half)&(yt<=hi)).mean()),3)}
    return result


def main() -> None:
    for pest in ("BPH", "RSB"):
        result = evaluate(pest)
        path = PEST_PARAMS[pest].bilstm_weights_path.parent / f"bilstm_{pest.lower()}_early_warning.json"
        path.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
