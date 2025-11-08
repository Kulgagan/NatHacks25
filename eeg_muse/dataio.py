
import os, json
import numpy as np
import pandas as pd
from .utils import sanitize_columns, detect_label_column, split_features_labels, save_json

def preprocess_split(input_csv: str, out_dir: str, train_size=0.8, seed=42):
    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(input_csv)
    df = sanitize_columns(df)
    label_col = detect_label_column(df)
    df = df.dropna(axis=0, how="any").reset_index(drop=True)
    X_all, y_all = split_features_labels(df, label_col)

    from sklearn.model_selection import StratifiedShuffleSplit
    sss = StratifiedShuffleSplit(n_splits=1, train_size=train_size, random_state=seed)
    train_idx, test_idx = next(sss.split(X_all, y_all))
    train_df, test_df = df.iloc[train_idx].reset_index(drop=True), df.iloc[test_idx].reset_index(drop=True)

    train_df.to_csv(os.path.join(out_dir,"train.csv"), index=False)
    test_df.to_csv(os.path.join(out_dir,"test.csv"), index=False)

    classes = sorted(df[label_col].astype(str).unique().tolist())
    feature_cols = train_df.drop(columns=[label_col]).select_dtypes(include=[np.number]).columns.tolist()
    save_json(os.path.join(out_dir,"classes.json"), {"classes": classes})
    save_json(os.path.join(out_dir,"feature_columns.json"), {"features": feature_cols})
    return label_col, classes, feature_cols
