import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from eeg_muse.model import evaluate_rf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test_csv', default='artifacts/test.csv')
    ap.add_argument('--artifacts_dir', default='artifacts')
    args = ap.parse_args()
    acc, f1m = evaluate_rf(args.test_csv, args.artifacts_dir)
    print('Accuracy:', round(acc,4), 'Macro F1:', round(f1m,4))
if __name__ == '__main__': main()
