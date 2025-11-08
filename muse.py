import time
import numpy as np
import pandas as pd
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, AggOperations

# ======== CONFIGURATION ========
INTERVAL_SECONDS = 15
OUTPUT_FILE = "data/muse_metrics_relax.xlsx"   # or "muse_metrics.csv"
BOARD_ID = BoardIds.MUSE_2_BOARD.value
# ===============================

def calculate_metrics(data, eeg_channels, sampling_rate):
    """Compute band powers and custom metrics."""
    # Prepare dictionary for results
    metrics = {}

    # Get per-channel band powers
    bands = {}
    for ch in eeg_channels:
        DataFilter.detrend(data[ch], AggOperations.MEAN.value)
        DataFilter.perform_bandpass(data[ch], sampling_rate, 1.0, 50.0, 4, FilterTypes.BUTTERWORTH.value, 0)
        psd = DataFilter.get_psd_welch(data[ch], nfft=256, overlap=128, sampling_rate=sampling_rate, window=0)
        bands[ch] = {
            "alpha": DataFilter.get_band_power(psd, 8.0, 13.0),
            "beta": DataFilter.get_band_power(psd, 13.0, 30.0),
            "theta": DataFilter.get_band_power(psd, 4.0, 8.0),
        }

    # Channel labels for Muse 2: TP9, AF7, AF8, TP10
    # EEG channel order varies, but BrainFlow gives us it directly.
    # We'll assume 0: TP9, 1: AF7, 2: AF8, 3: TP10
    TP9, AF7, AF8, TP10 = eeg_channels

    # Individual metrics
    metrics["af7_alpha"] = bands[AF7]["alpha"]
    metrics["af8_alpha"] = bands[AF8]["alpha"]
    metrics["af7_beta"] = bands[AF7]["beta"]
    metrics["af8_beta"] = bands[AF8]["beta"]
    metrics["tp9_theta"] = bands[TP9]["theta"]
    metrics["tp10_theta"] = bands[TP10]["theta"]

    # Derived metrics
    metrics["alpha_beta_ratio"] = (bands[AF7]["alpha"] + bands[AF8]["alpha"]) / (
        bands[AF7]["beta"] + bands[AF8]["beta"] + 1e-6
    )
    metrics["alpha_asymmetry"] = bands[AF7]["alpha"] - bands[AF8]["alpha"]

    return metrics


def main():
    params = BrainFlowInputParams()
    # params.serial_port = ''  # if using serial
    # params.mac_address = 'XX:XX:XX:XX:XX:XX'  # optional for Muse 2 via BLE
    board = BoardShim(BOARD_ID, params)

    print("Connecting to Muse 2 headset...")
    board.prepare_session()
    board.start_stream()

    eeg_channels = BoardShim.get_eeg_channels(BOARD_ID)
    sampling_rate = BoardShim.get_sampling_rate(BOARD_ID)

    print("Streaming EEG data... press Ctrl+C to stop.")

    all_records = []

    try:
        while True:
            time.sleep(INTERVAL_SECONDS)
            data = board.get_current_board_data(sampling_rate * INTERVAL_SECONDS)
            if data.shape[1] == 0:
                print("No data received in this interval.")
                continue

            metrics = calculate_metrics(data, eeg_channels, sampling_rate)
            metrics["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            all_records.append(metrics)

            # Print live update
            print(f"[{metrics['timestamp']}] Metrics: {metrics}")

            # Save continuously to spreadsheet
            df = pd.DataFrame(all_records)
            if OUTPUT_FILE.endswith(".csv"):
                df.to_csv(OUTPUT_FILE, index=False)
            else:
                df.to_excel(OUTPUT_FILE, index=False)

    except KeyboardInterrupt:
        print("\nStopping stream...")

    finally:
        board.stop_stream()
        board.release_session()
        print(f"Data saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
