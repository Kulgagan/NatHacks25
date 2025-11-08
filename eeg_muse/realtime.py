
import time, os, json, numpy as np
# delayed import of pylsl
from .features import extract_window_features, align_features_to_training

def stream_and_predict(artifacts_dir: str, model_path: str = None,
                       stream_name: str = "Muse",
                       channels = ("TP9","AF7","AF8","TP10"),
                       window_sec: float = 2.0,
                       step_sec: float = 0.5,
                       fallback_sf: float = 256.0):
    import joblib
    if model_path is None: model_path = os.path.join(artifacts_dir,"random_forest.joblib")
    classes = json.load(open(os.path.join(artifacts_dir, "classes.json")))["classes"]
    features = json.load(open(os.path.join(artifacts_dir, "feature_columns.json")))["features"]
    clf = joblib.load(model_path)

    from pylsl import StreamInlet, resolve_byprop
    streams = resolve_byprop('type', 'EEG', timeout=5)
    sel = None
    for s in streams:
        if stream_name.lower() in s.name().lower(): sel=s; break
    if sel is None and streams: sel=streams[0]
    inlet = StreamInlet(sel, max_buflen=60)
    fs = sel.nominal_srate() if sel.nominal_srate()>0 else fallback_sf

    win = int(window_sec * fs); step = int(step_sec * fs); buf = []
    print(f'Connected: {sel.name()} @ {fs} Hz | Channels expected: {channels}')
    print('Streaming... Ctrl+C to stop.')
    try:
        while True:
            sample, ts = inlet.pull_sample(timeout=5.0)
            if sample is None:
                print('No sample received. Is muselsl streaming?'); time.sleep(1); continue
            x = sample[:len(channels)]
            buf.append(x)
            if len(buf) >= win:
                window = np.array(buf[-win:])
                feats = extract_window_features(window, channels, fs)
                X_row, missing = align_features_to_training(feats, features)
                probs = clf.predict_proba(X_row)[0]
                pred = clf.predict(X_row)[0]
                label = classes[int(pred)] if isinstance(pred, (int, np.integer)) else str(pred)
                yield label, {classes[i]: float(probs[i]) for i in range(len(classes))}
                buf = buf[-(win - step):]
    except KeyboardInterrupt:
        return
