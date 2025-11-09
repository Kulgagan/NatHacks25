# ============================================================================
# IMPORTS
# ============================================================================
import json
import asyncio
import threading
import time
import queue
import logging
import math
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowError
from brainflow.data_filter import DataFilter, FilterTypes, AggOperations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
BOARD_ID = BoardIds.MUSE_2_BOARD.value
UPDATE_INTERVAL = 2  # Update every 2 seconds
WINDOW_SECONDS = 3   # Use 3 seconds of data

# ============================================================================
# BRAINFLOW FUNCTIONS (only called when connect button is pressed)
# ============================================================================
def calculate_alpha_beta_ratio(data, eeg_channels, sampling_rate):
    """Calculate alpha/beta ratio from EEG data."""
    try:
        if data.shape[1] == 0:
            return None
        
        bands = {}
        for ch in eeg_channels:
            DataFilter.detrend(data[ch], AggOperations.MEAN.value)
            DataFilter.perform_bandpass(data[ch], sampling_rate, 1.0, 50.0, 4, FilterTypes.BUTTERWORTH.value, 0)
            psd = DataFilter.get_psd_welch(data[ch], nfft=256, overlap=128, sampling_rate=sampling_rate, window=0)
            bands[ch] = {
                "alpha": DataFilter.get_band_power(psd, 8.0, 13.0),
                "beta": DataFilter.get_band_power(psd, 13.0, 30.0),
            }
        
        TP9, AF7, AF8, TP10 = eeg_channels[0], eeg_channels[1], eeg_channels[2], eeg_channels[3]
        total_alpha = bands[AF7]["alpha"] + bands[AF8]["alpha"]
        total_beta = bands[AF7]["beta"] + bands[AF8]["beta"]
        
        if total_beta < 1e-6:
            return None
        
        return total_alpha / (total_beta + 1e-6)
    except Exception as e:
        logger.error(f"Error calculating ratio: {e}")
        return None

def ratio_to_focus_percentage(ratio):
    """Convert alpha/beta ratio to focus percentage (0-100%)."""
    if ratio is None:
        return 0.0
    
    # Map ratio [0.2, 3.0] to [100%, 0%] (inverted)
    # ratio = max(0.2, min(3.0, ratio))
    # normalized = 1.0 - ((ratio - 0.2) / 2.8)
    # return max(0.0, min(100.0, normalized * 100.0))

    # Parameters (dynamic midpoint learned via calibration)
    try:
        _mp = getattr(device_state, "calibration_midpoint", None)
        if _mp is None and hasattr(device_state, "calibration"):
            _mp = device_state.calibration.get("midpoint", 0.7)
        midpoint = float(_mp) if _mp is not None else 0.7
    except Exception:
        midpoint = 0.7
    steepness = 3.0     # controls how quickly focus changes near midpoint

    focus_score = 1 / (1 + math.exp(steepness * (ratio - midpoint)))

    # Scale to 0–100%
    focus_percent = focus_score * 100
    return round(focus_percent, 2)

# ============================================================================
# DEVICE STATE
# ============================================================================
class DeviceState:
    def __init__(self):
        self.board: Optional[BoardShim] = None
        self.is_connected = False
        self.is_streaming = False
        self.focus_percentage = 0.0
        self.alpha_beta_ratio = 0.0
        self.eeg_channels = None
        self.sampling_rate = 256
        self.websocket_clients = []
        self.streaming_thread: Optional[threading.Thread] = None
        self.update_queue = queue.Queue()
        # Calibration state
        self.calibration = {
            "phase": None,        # None | "relax" | "task"
            "start_time": 0.0,
            "relax": [],         # list of ratios
            "task": [],          # list of ratios
            "midpoint": 0.7,
        }
        self.calibration_midpoint = None

device_state = DeviceState()

def streaming_worker():
    """Background thread - only runs after connect button is pressed."""
    logger.info("Streaming worker started")
    while device_state.is_streaming and device_state.is_connected:
        try:
            if device_state.board is None:
                time.sleep(UPDATE_INTERVAL)
                continue
            
            samples_needed = int(device_state.sampling_rate * WINDOW_SECONDS)
            data = device_state.board.get_current_board_data(samples_needed)
            
            if data.shape[1] < samples_needed:
                time.sleep(0.1)
                continue
            
            ratio = calculate_alpha_beta_ratio(data, device_state.eeg_channels, device_state.sampling_rate)
            
            if ratio is not None:
                device_state.alpha_beta_ratio = ratio
                device_state.focus_percentage = ratio_to_focus_percentage(ratio)
                # If calibration is active, collect samples for the current phase
                try:
                    cal = device_state.calibration
                    phase = cal.get("phase") if isinstance(cal, dict) else None
                    if phase in ("relax", "task"):
                        buf = cal.get(phase)
                        if isinstance(buf, list) and len(buf) < 1024:
                            buf.append(float(ratio))
                except Exception:
                    pass
                
                try:
                    device_state.update_queue.put_nowait({
                        "focus_percentage": device_state.focus_percentage,
                        "alpha_beta_ratio": device_state.alpha_beta_ratio,
                        "timestamp": time.time()
                    })
                except queue.Full:
                    pass
            
            time.sleep(UPDATE_INTERVAL)
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            time.sleep(1.0)
    logger.info("Streaming worker stopped")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(title="Muse 2 Focus Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# WEBSOCKET HELPERS
# ============================================================================
async def broadcast_to_clients(message: dict):
    """Broadcast to all WebSocket clients."""
    if not device_state.websocket_clients:
        return
    
    formatted = {
        "focus_percentage": round(message["focus_percentage"], 2),
        "alpha_beta_ratio": round(message["alpha_beta_ratio"], 4),
        "timestamp": message["timestamp"]
    }
    
    disconnected = []
    for client in device_state.websocket_clients:
        try:
            await client.send_json(formatted)
        except:
            disconnected.append(client)
    
    for client in disconnected:
        if client in device_state.websocket_clients:
            device_state.websocket_clients.remove(client)

async def process_update_queue():
    """Process updates from streaming worker."""
    while True:
        try:
            message = device_state.update_queue.get(timeout=0.1)
            await broadcast_to_clients(message)
        except queue.Empty:
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Queue error: {e}")
            await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup():
    asyncio.create_task(process_update_queue())

# ============================================================================
# API ENDPOINTS
# ============================================================================
class ConnectRequest(BaseModel):
    mac_address: Optional[str] = None
    serial_port: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Muse 2 Focus Tracker API"}

@app.get("/status")
async def get_status():
    return {
        "status": "connected" if device_state.is_connected else "disconnected",
        "is_connected": device_state.is_connected,
        "is_streaming": device_state.is_streaming,
        "focus_percentage": device_state.focus_percentage,
        "alpha_beta_ratio": device_state.alpha_beta_ratio
    }

@app.post("/connect")
async def connect_device(request: ConnectRequest):
    """Connect to Muse 2 - BrainFlow only runs here when button is clicked."""
    if device_state.is_connected:
        return {"message": "Already connected", "status": "connected"}
    
    try:
        # Only initialize BrainFlow when connect button is pressed
        logger.info("Connecting to Muse 2...")
        params = BrainFlowInputParams()
        if request.mac_address:
            params.mac_address = request.mac_address
        elif request.serial_port:
            params.serial_port = request.serial_port
        params.timeout = 15
        
        board = BoardShim(BOARD_ID, params)
        board.prepare_session()
        board.start_stream()
        
        eeg_channels = BoardShim.get_eeg_channels(BOARD_ID)
        sampling_rate = BoardShim.get_sampling_rate(BOARD_ID)
        
        device_state.board = board
        device_state.is_connected = True
        device_state.eeg_channels = eeg_channels
        device_state.sampling_rate = sampling_rate
        device_state.is_streaming = True
        
        # Start streaming worker (runs BrainFlow processing)
        device_state.streaming_thread = threading.Thread(target=streaming_worker, daemon=True)
        device_state.streaming_thread.start()
        
        logger.info("Muse 2 connected and streaming started!")
        return {"message": "Connected", "status": "connected", "device": "Muse 2"}
    
    except BrainFlowError as e:
        logger.error(f"BrainFlow error: {e}")
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/disconnect")
async def disconnect_device():
    """Disconnect from Muse 2."""
    if not device_state.is_connected:
        return {"message": "Not connected", "status": "disconnected"}
    
    device_state.is_streaming = False
    
    if device_state.streaming_thread and device_state.streaming_thread.is_alive():
        device_state.streaming_thread.join(timeout=2.0)
    
    if device_state.board:
        try:
            device_state.board.stop_stream()
            device_state.board.release_session()
        except:
            pass
    
    device_state.board = None
    device_state.is_connected = False
    device_state.focus_percentage = 0.0
    device_state.alpha_beta_ratio = 0.0
    
    logger.info("Disconnected")
    return {"message": "Disconnected", "status": "disconnected"}

@app.get("/focus")
async def get_focus():
    return {
        "focus_percentage": round(device_state.focus_percentage, 2),
        "alpha_beta_ratio": round(device_state.alpha_beta_ratio, 4),
        "is_connected": device_state.is_connected
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for live focus updates."""
    await websocket.accept()
    device_state.websocket_clients.append(websocket)
    
    try:
        await websocket.send_json({
            "focus_percentage": round(device_state.focus_percentage, 2),
            "alpha_beta_ratio": round(device_state.alpha_beta_ratio, 4),
            "is_connected": device_state.is_connected
        })
        
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "keepalive"})
            except WebSocketDisconnect:
                break
    except:
        pass
    finally:
        if websocket in device_state.websocket_clients:
            device_state.websocket_clients.remove(websocket)

@app.on_event("shutdown")
async def shutdown():
    if device_state.is_connected:
        device_state.is_streaming = False
        if device_state.board:
            try:
                device_state.board.stop_stream()
                device_state.board.release_session()
            except:
                pass



# ================= RL MUSIC SERVICE =====================
from rl_music import MusicSession
music_sessions = {}

@app.websocket("/ws/music")
async def music_ws(ws: WebSocket):
    await ws.accept()
    session = MusicSession()
    client_id = id(ws)
    music_sessions[client_id] = session

    send_task = None
    recv_task = None
    stop_flag = False

    async def sender():
        # stream binary PCM chunks forever until closed
        try:
            while True:
                data = session.next_chunk()
                await ws.send_bytes(data)
                await asyncio.sleep(0.0)  # yield
        except Exception as e:
            pass

    async def receiver():
        # receive control messages (JSON text)
        try:
            while True:
                msg = await ws.receive_text()
                try:
                    payload = json.loads(msg)
                except Exception:
                    continue
                t = payload.get("type")
                if t == "focus":
                    session.set_focus(float(payload.get("value", 0.0)))
                elif t == "volume":
                    session.volume = float(payload.get("value", 0.8))
                elif t == "skip":
                    session.skip()
                elif t == "profile":
                    try:
                        prof = payload.get("profile", "none")
                        session.apply_profile(str(prof))
                    except Exception:
                        pass
                    try:
                        overrides = payload.get("overrides") or payload.get("params")
                        if isinstance(overrides, dict):
                            session.apply_overrides(overrides)
                    except Exception:
                        pass
                elif t == "stop":
                    break
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    try:
        send_task = asyncio.create_task(sender())
        recv_task = asyncio.create_task(receiver())
        await asyncio.wait([send_task, recv_task], return_when=asyncio.FIRST_COMPLETED)
    finally:
        if send_task: send_task.cancel()
        if recv_task: recv_task.cancel()
        music_sessions.pop(client_id, None)
        try:
            await ws.close()
        except Exception:
            pass
# ========================================================

# ================= CALIBRATION API ======================
class CalibPhase(BaseModel):
    phase: str
    duration_sec: Optional[int] = None

@app.post("/calibration/start")
async def calibration_start(req: CalibPhase):
    phase = (req.phase or "").lower()
    if phase not in ("relax", "task"):
        raise HTTPException(status_code=400, detail="phase must be 'relax' or 'task'")
    cal = device_state.calibration
    cal["phase"] = phase
    cal["start_time"] = time.time()
    cal[phase] = []
    return {"status": "ok", "phase": phase}

@app.post("/calibration/stop")
async def calibration_stop(req: CalibPhase):
    phase = (req.phase or "").lower()
    if phase not in ("relax", "task"):
        raise HTTPException(status_code=400, detail="phase must be 'relax' or 'task'")
    cal = device_state.calibration
    if cal.get("phase") == phase:
        cal["phase"] = None
    samples = cal.get(phase, []) or []
    import statistics
    stats = {
        "count": len(samples),
        "mean": float(statistics.fmean(samples)) if samples else None,
        "median": float(statistics.median(samples)) if samples else None,
    }
    return {"status": "ok", "phase": phase, "stats": stats}

@app.post("/calibration/commit")
async def calibration_commit():
    cal = device_state.calibration
    relax = cal.get("relax", []) or []
    task = cal.get("task", []) or []
    if not relax or not task:
        raise HTTPException(status_code=400, detail="Both relax and task samples are required")
    import statistics
    relax_mean = statistics.fmean(relax)
    task_mean = statistics.fmean(task)
    midpoint = float((relax_mean + task_mean) / 2.0)
    cal["midpoint"] = midpoint
    device_state.calibration_midpoint = midpoint
    return {
        "status": "ok",
        "midpoint": midpoint,
        "relax_mean": float(relax_mean),
        "task_mean": float(task_mean),
        "counts": {"relax": len(relax), "task": len(task)},
    }

@app.get("/calibration/status")
async def calibration_status():
    cal = device_state.calibration
    elapsed = 0.0
    if cal.get("phase"):
        try:
            elapsed = time.time() - float(cal.get("start_time") or 0.0)
        except Exception:
            elapsed = 0.0
    return {
        "phase": cal.get("phase"),
        "elapsed": round(elapsed, 2),
        "counts": {"relax": len(cal.get("relax", []) or []), "task": len(cal.get("task", []) or [])},
        "midpoint": cal.get("midpoint"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)