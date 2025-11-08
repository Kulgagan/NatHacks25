
import os, json, numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from .utils import detect_label_column, split_features_labels, save_json

def train_rf(train_csv: str, artifacts_dir: str, estimators=300, seed=42):
    os.makedirs(artifacts_dir, exist_ok=True)
    df = pd.read_csv(train_csv)
    label_col = detect_label_column(df)
    classes = sorted(df[label_col].astype(str).unique().tolist())
    class_to_idx = {c:i for i,c in enumerate(classes)}
    y = df[label_col].astype(str).map(class_to_idx).values
    X = df.drop(columns=[label_col]).select_dtypes(include=[np.number]).values

    clf = RandomForestClassifier(n_estimators=estimators, random_state=seed, n_jobs=-1, class_weight="balanced")
    clf.fit(X, y)
    joblib.dump(clf, os.path.join(artifacts_dir,"random_forest.joblib"))
    return clf, classes

def evaluate_rf(test_csv: str, artifacts_dir: str):
    import joblib
    df = pd.read_csv(test_csv)
    label_col = detect_label_column(df)
    classes = json.load(open(os.path.join(artifacts_dir,"classes.json")))["classes"]
    class_to_idx = {c:i for i,c in enumerate(classes)}
    y_true = df[label_col].astype(str).map(class_to_idx).values
    X = df.drop(columns=[label_col]).select_dtypes(include=[np.number]).values
    clf = joblib.load(os.path.join(artifacts_dir,"random_forest.joblib"))
    y_pred = clf.predict(X)
    acc = float(accuracy_score(y_true, y_pred))
    f1m = float(f1_score(y_true, y_pred, average="macro"))
    report = classification_report(y_true, y_pred, target_names=classes, output_dict=True)
    save_json(os.path.join(artifacts_dir,"metrics_random_forest.json"),
              {"accuracy": acc, "macro_f1": f1m, "classification_report": report})

    # confusion matrix image
    try:
        import matplotlib.pyplot as plt
        cm = confusion_matrix(y_true, y_pred, labels=list(range(len(classes))))
        plt.figure()
        plt.imshow(cm, interpolation='nearest')
        plt.title('Confusion matrix - RandomForest')
        tick = np.arange(len(classes))
        plt.xticks(tick, classes, rotation=45, ha='right'); plt.yticks(tick, classes)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, str(cm[i,j]), ha='center', va='center')
        plt.xlabel('Predicted'); plt.ylabel('True'); plt.tight_layout()
        plt.savefig(os.path.join(artifacts_dir,'confusion_random_forest.png'), dpi=150); plt.close()
    except Exception:
        pass
    return acc, f1m

def predict_csv(input_csv: str, artifacts_dir: str, out_csv: str):
    import joblib
    df = pd.read_csv(input_csv)
    classes = json.load(open(os.path.join(artifacts_dir,"classes.json")))["classes"]
    try:
        label_col = detect_label_column(df)
        X = df.drop(columns=[label_col]).select_dtypes(include=[np.number])
    except Exception:
        X = df.select_dtypes(include=[np.number])
    clf = joblib.load(os.path.join(artifacts_dir,"random_forest.joblib"))
    preds = clf.predict(X.values)
    proba = clf.predict_proba(X.values)
    out = pd.DataFrame({"pred_label":[classes[int(i)] for i in preds]})
    for i,c in enumerate(classes): out[f"p_{c}"] = proba[:,i]
    out.to_csv(out_csv, index=False); return out
