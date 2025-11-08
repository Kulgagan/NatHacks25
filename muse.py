import time
import numpy as np
import pandas as pd
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, AggOperations

# ======== CONFIGURATION ========
INTERVAL_SECONDS = 15
OUTPUT_FILE = "muse_metrics_relax.xlsx"   # or "muse_metrics.csv"
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

# import time
# import csv
# import numpy as np
# import platform
# import sys
# import threading
# from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowError
# from brainflow.data_filter import DataFilter, WindowOperations
#
# # ----------- USER SETTINGS -----------
# MUSE_MAC = "00:55:da:b5:5f:d1"  # Replace with your Muse's MAC address
# BOARD_ID = BoardIds.MUSE_2_BOARD.value
# WINDOW_SEC = 2
# LOG_INTERVAL = 30
# SAMPLE_RATE = 256
# CSV_FILE = "eeg_data.csv"
# # -------------------------------------
#
# running = True  # global flag to control loop
#
#
# # ----------- Background Input Thread -----------
# def input_listener():
#     global running
#     print("💡 Press 'c' then Enter to stop.")
#     while running:
#         ch = input().strip().lower()
#         if ch == "c":
#             print("🛑 'c' pressed — stopping stream...")
#             running = False
#             break
#
#
# # ----------- Band Power Calculation -----------
# def band_power(channel_data, fs, band):
#     nfft = min(256, len(channel_data))
#     if len(channel_data) < nfft:
#         return 0.0
#     overlap = nfft // 2
#     try:
#         psd = DataFilter.get_psd_welch(
#             channel_data, fs, nfft, overlap, WindowOperations.HANNING
#         )
#         freqs = np.linspace(0, fs / 2, len(psd))
#         idx_band = np.logical_and(freqs >= band[0], freqs <= band[1])
#         return np.sum(psd[idx_band]) if np.any(idx_band) else 0.0
#     except Exception as e:
#         print(f"⚠️ PSD error: {e}")
#         return 0.0
#
#
# # ----------- Main Program -----------
# if __name__ == "__main__":
#     BoardShim.enable_dev_board_logger()
#
#     params = BrainFlowInputParams()
#     params.mac_address = MUSE_MAC
#     params.timeout = 15
#
#     board = BoardShim(BOARD_ID, params)
#
#     try:
#         print("🔹 Preparing Muse 2 session...")
#         board.prepare_session()
#         board.start_stream()
#         print("✅ Muse 2 streaming started!")
#         print("⏳ Filling buffer...")
#         time.sleep(WINDOW_SEC * 2)
#
#         # Start background input listener
#         threading.Thread(target=input_listener, daemon=True).start()
#
#         samples_needed = int(WINDOW_SEC * SAMPLE_RATE)
#         eeg_channels = BoardShim.get_eeg_channels(BOARD_ID)
#         tp9, af7, af8, tp10 = eeg_channels[0], eeg_channels[1], eeg_channels[2], eeg_channels[3]
#
#         alpha_band, beta_band, theta_band = (8, 13), (13, 30), (4, 8)
#         accumulated_data = {k: [] for k in [
#             "af7_alpha", "af8_alpha", "af7_beta", "af8_beta",
#             "tp9_theta", "tp10_theta", "alpha_beta_ratio", "alpha_asymmetry"
#         ]}
#         last_log_time = time.time()
#         window_count = 0
#
#         with open(CSV_FILE, "w", newline="") as file:
#             writer = csv.writer(file)
#             writer.writerow([
#                 "timestamp",
#                 "af7_alpha", "af8_alpha",
#                 "af7_beta", "af8_beta",
#                 "tp9_theta", "tp10_theta",
#                 "alpha_beta_ratio", "alpha_asymmetry"
#             ])
#             file.flush()
#
#             while True:
#                 if not running:
#                     break  # immediately exit if user pressed 'c'
#
#                 data = board.get_current_board_data(samples_needed)
#                 if data.shape[1] < samples_needed:
#                     time.sleep(0.1)
#                     if not running:
#                         break  # check again after sleep
#                     continue
#
#                 af7_data, af8_data = data[af7, :], data[af8, :]
#                 tp9_data, tp10_data = data[tp9, :], data[tp10, :]
#
#                 af7_alpha = band_power(af7_data, SAMPLE_RATE, alpha_band)
#                 af8_alpha = band_power(af8_data, SAMPLE_RATE, alpha_band)
#                 af7_beta = band_power(af7_data, SAMPLE_RATE, beta_band)
#                 af8_beta = band_power(af8_data, SAMPLE_RATE, beta_band)
#                 tp9_theta = band_power(tp9_data, SAMPLE_RATE, theta_band)
#                 tp10_theta = band_power(tp10_data, SAMPLE_RATE, theta_band)
#
#                 total_alpha = af7_alpha + af8_alpha
#                 total_beta = af7_beta + af8_beta
#                 alpha_beta_ratio = total_alpha / (total_beta + 1e-10)
#                 alpha_asymmetry = af7_alpha - af8_alpha
#
#                 for k, v in [
#                     ("af7_alpha", af7_alpha), ("af8_alpha", af8_alpha),
#                     ("af7_beta", af7_beta), ("af8_beta", af8_beta),
#                     ("tp9_theta", tp9_theta), ("tp10_theta", tp10_theta),
#                     ("alpha_beta_ratio", alpha_beta_ratio),
#                     ("alpha_asymmetry", alpha_asymmetry)
#                 ]:
#                     accumulated_data[k].append(v)
#
#                 window_count += 1
#                 print(f"🧠 Window {window_count}: α/β={alpha_beta_ratio:.3f}, Asym={alpha_asymmetry:.3f}")
#
#                 if time.time() - last_log_time >= LOG_INTERVAL:
#                     timestamp = time.time()
#                     avg = {k: np.mean(v) for k, v in accumulated_data.items()}
#                     writer.writerow([
#                         timestamp,
#                         avg["af7_alpha"], avg["af8_alpha"],
#                         avg["af7_beta"], avg["af8_beta"],
#                         avg["tp9_theta"], avg["tp10_theta"],
#                         avg["alpha_beta_ratio"], avg["alpha_asymmetry"]
#                     ])
#                     file.flush()
#                     print("📊 Logged average EEG data.")
#                     accumulated_data = {k: [] for k in accumulated_data}
#                     last_log_time = time.time()
#
#                 time.sleep(0.1)
#
#
#     except BrainFlowError as e:
#         print(f"❌ BrainFlow error: {e}")
#     except KeyboardInterrupt:
#         print("🛑 Interrupted manually.")
#     except Exception as e:
#         print(f"❌ Unexpected error: {e}")
#     finally:
#         try:
#             print("⚙️ Cleaning up...")
#             board.stop_stream()
#             board.release_session()
#         except Exception as e:
#             print(f"⚠️ Cleanup error: {e}")
#         print(f"💾 Data saved to {CSV_FILE}")
#         print("🎯 Program exited successfully.")
