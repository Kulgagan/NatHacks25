
import re, json
import numpy as np
import pandas as pd

LABEL_CANDIDATES = ["label","state","target","class","y"]

def sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"\s+","_", str(c).strip()) for c in df.columns]
    return df

def detect_label_column(df: pd.DataFrame) -> str:
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in LABEL_CANDIDATES:
        if cand in cols_lower:
            return cols_lower[cand]
    for c in df.columns:
        if df[c].dtype == "object" and 2 <= df[c].nunique(dropna=True) <= 6:
            return c
    return df.columns[-1]

def split_features_labels(df: pd.DataFrame, label_col: str):
    X = df.drop(columns=[label_col])
    y = df[label_col]
    X = X.select_dtypes(include=[np.number])
    return X, y

def save_json(path: str, data: dict) -> None:
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)
