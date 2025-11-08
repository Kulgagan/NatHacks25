import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from eeg_muse.model import predict_csv

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input_csv', default='artifacts/test.csv')
    ap.add_argument('--artifacts_dir', default='artifacts')
    ap.add_argument('--out_csv', default='artifacts/preds_rf.csv')
    args = ap.parse_args()
    df = predict_csv(args.input_csv, args.artifacts_dir, args.out_csv)
    print('Wrote', args.out_csv, 'with', len(df), 'rows.')
if __name__ == '__main__': main()
