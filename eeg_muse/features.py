
import numpy as np
from scipy.signal import welch

BANDS = {'delta':(1,4),'theta':(4,8),'alpha':(8,13),'beta':(13,30),'gamma':(30,45)}

def bandpower_welch(x, fs, fmin, fmax):
    f, Pxx = welch(x, fs=fs, nperseg=min(len(x), 256))
    idx = (f>=fmin) & (f<=fmax)
    return float(np.trapz(Pxx[idx], f[idx])) if idx.any() else 0.0

def extract_window_features(window, ch_names, fs):
    arr = np.asarray(window)
    feats = {}
    for ci, ch in enumerate(ch_names):
        x = arr[:, ci]
        feats[f'{ch}_mean'] = float(np.mean(x))
        feats[f'{ch}_std']  = float(np.std(x))
        feats[f'{ch}_var']  = float(np.var(x))
        feats[f'{ch}_min']  = float(np.min(x))
        feats[f'{ch}_max']  = float(np.max(x))
        feats[f'{ch}_rms']  = float(np.sqrt(np.mean(x**2)))
        for band, (lo, hi) in BANDS.items():
            feats[f'{ch}_bp_{band}'] = bandpower_welch(x, fs, lo, hi)
    return feats

def align_features_to_training(feature_dict, feature_list):
    row, missing = [], []
    for f in feature_list:
        if f in feature_dict: row.append(feature_dict[f])
        else: row.append(0.0); missing.append(f)
    return np.array(row).reshape(1,-1), missing
