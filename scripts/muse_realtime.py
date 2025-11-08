import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse, time
from eeg_muse.realtime import stream_and_predict
from eeg_muse.config import DEFAULTS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--artifacts_dir', default='artifacts')
    ap.add_argument('--model', default=None)
    ap.add_argument('--stream_name', default=DEFAULTS['lsl_stream_name'])
    ap.add_argument('--channels', nargs='+', default=DEFAULTS['lsl_channels'])
    ap.add_argument('--window_sec', type=float, default=DEFAULTS['lsl_window_sec'])
    ap.add_argument('--step_sec', type=float, default=DEFAULTS['lsl_step_sec'])
    ap.add_argument('--sf', type=float, default=DEFAULTS['lsl_fallback_sf'])
    args = ap.parse_args()
    for label, probs in stream_and_predict(args.artifacts_dir, args.model, args.stream_name,
                                           tuple(args.channels), args.window_sec, args.step_sec, args.sf):
        prob_str = ', '.join([f'{k}: {v:.2f}' for k,v in probs.items()])
        print(f'[{time.strftime("%H:%M:%S")}] {label} | {prob_str}')
if __name__ == '__main__': main()
