#RUN IDE AS ADMINISTRATOR OR ELSE IT WILL NOT CONNECT!!!!!!!!!!!!!!
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowError
import time
import matplotlib.pyplot as plt

#RUN AS ADMINISTRATOR OR ELSE IT WILL NOT CONNECT!!!!!!!!!!!!!!

# Enable BrainFlow logs (helpful for debugging)
BoardShim.enable_dev_board_logger()

# --- Connection parameters ---
params = BrainFlowInputParams()
params.mac_address = "00:55:da:b5:5f:d1"  # replace with your Muse's MAC address
params.serial_port = ""                   # not used for BLE devices
params.timeout = 10                       # seconds for discovery

# --- Initialize Muse 2 board ---
board_id = BoardIds.MUSE_2_BOARD.value
board = BoardShim(board_id, params)

try:
    print("🔹 Preparing Muse 2 session...")
    board.prepare_session()

    print("🔹 Starting data stream...")
    board.start_stream()

    print("✅ Streaming EEG data for 10 seconds...")
    time.sleep(10)

    print("🛑 Stopping stream...")
    board.stop_stream()

    # Get all the data collected so far
    data = board.get_board_data()
    print("📊 Data shape:", data.shape)

    eeg_channels = BoardShim.get_eeg_channels(BoardIds.MUSE_2_BOARD.value)
    eeg_data = data[eeg_channels, :]
    print(eeg_data.shape)

    plt.plot(eeg_data[0][:512])  # first 2 seconds of TP9
    plt.title("Muse 2 EEG Channel (TP9)")
    plt.xlabel("Samples")
    plt.ylabel("Amplitude (µV)")
    plt.show()



except BrainFlowError as e:
    print(f"❌ BrainFlowError: {e}")
    print("\nTroubleshooting tips:")
    print("  - Make sure Muse 2 is NOT connected to your phone.")
    print("  - Ensure Muse 2 is blinking and ready to pair.")
    print("  - Run this script as Administrator (for Bluetooth access).")
    print("  - Keep the headset close to your laptop.")
    print("  - Double-check the MAC address above matches your Muse.")
finally:
    print("🔹 Releasing session...")
    board.release_session()
