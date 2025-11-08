import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse, os, json
from eeg_muse.model import train_rf
from eeg_muse.config import DEFAULTS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train_csv', default='artifacts/train.csv')
    ap.add_argument('--artifacts_dir', default='artifacts')
    ap.add_argument('--estimators', type=int, default=DEFAULTS['rf_estimators'])
    ap.add_argument('--seed', type=int, default=DEFAULTS['seed'])
    args = ap.parse_args()
    train_rf(args.train_csv, args.artifacts_dir, args.estimators, args.seed)
if __name__ == '__main__': main()
