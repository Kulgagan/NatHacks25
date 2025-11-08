<<<<<<< HEAD
# NatHacks25
=======

# Muse Mental State (RandomForest)

End-to-end project to train on your EEG dataset and run realtime mental-state inference with a **Muse 2** via **LSL**.

## Project layout
```
muse-mental-state/
├── data/
│   └── mental-state.csv
├── artifacts/                # models & metadata
├── notebooks/
│   └── EEG_Mental_State_RF_Pipeline.ipynb
├── scripts/
│   ├── preprocess.py
│   ├── train_rf.py
│   ├── evaluate.py
│   ├── predict.py
│   ├── muse_realtime.py      # terminal realtime
│   └── muse_dashboard.py     # Streamlit realtime dashboard
└── src/eeg_muse/
    ├── __init__.py
    ├── config.py
    ├── utils.py
    ├── features.py
    ├── dataio.py
    ├── model.py
    └── realtime.py
```

## 1) Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) Train (RandomForest)
```bash
# split + metadata
python scripts/preprocess.py --input_csv data/mental-state.csv --out_dir artifacts
# train RF
python scripts/train_rf.py --train_csv artifacts/train.csv --artifacts_dir artifacts
# evaluate
python scripts/evaluate.py --test_csv artifacts/test.csv --artifacts_dir artifacts
# predict sample
python scripts/predict.py --input_csv artifacts/test.csv --artifacts_dir artifacts --out_csv artifacts/preds_rf.csv
```

## 3) Realtime with Muse 2
Open a new terminal and start a Muse LSL stream:
```bash
muselsl stream
# optional: muselsl view
```

Then run terminal realtime:
```bash
python scripts/muse_realtime.py --artifacts_dir artifacts --stream_name Muse --channels TP9 AF7 AF8 TP10 --window_sec 2.0 --step_sec 0.5
```

Or run a simple dashboard:
```bash
streamlit run scripts/muse_dashboard.py
```

**Output:** lines like `relaxed | relaxed: 0.74, concentrating: 0.18, neutral: 0.08` (these are your class probabilities/"weights").

## Notes
- Labels are auto-detected; only numeric columns are used as features.
- `classes.json` and `feature_columns.json` ensure realtime feature alignment.
- For publication, please cite:
  - Bird et al., 2018, *A study on mental state classification using EEG-based brain-machine interface*.
  - Bird et al., 2019, *Mental emotional sentiment classification with an EEG-based brain-machine interface*.
>>>>>>> fb57563782b18769bce34ed04c971fa4f5421dd0
