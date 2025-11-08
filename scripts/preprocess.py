import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse, os
from eeg_muse.dataio import preprocess_split
from eeg_muse.config import DEFAULTS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input_csv', default='data/mental-state.csv')
    ap.add_argument('--out_dir', default='artifacts')
    ap.add_argument('--train_size', type=float, default=DEFAULTS['train_size'])
    ap.add_argument('--seed', type=int, default=DEFAULTS['seed'])
    args = ap.parse_args()
    preprocess_split(args.input_csv, args.out_dir, args.train_size, args.seed)
if __name__ == '__main__': main()
