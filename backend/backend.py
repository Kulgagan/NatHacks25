from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import threading
import time
import queue
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowError
from brainflow.data_filter import DataFilter, FilterTypes, AggOperations
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Muse 2 Focus Tracker API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class DeviceState:
    def __init__(self):
        self.board: Optional[BoardShim] = None
        self.is_connected = False
        self.is_streaming = False
        self.current_focus_percentage = 0.0
        self.alpha_beta_ratio = 0.0
        self.eeg_channels = None
        self.sampling_rate = 256
        self.websocket_clients: list[WebSocket] = []
        self.streaming_thread: Optional[threading.Thread] = None
        self.update_queue: queue.Queue = queue.Queue()
        
device_state = DeviceState()

# Configuration
BOARD_ID = BoardIds.MUSE_2_BOARD.value
UPDATE_INTERVAL = 2.0  # Update focus percentage every 2 seconds
WINDOW_SECONDS = 3.0  # Use 3 seconds of data for calculation

# Response models
class StatusResponse(BaseModel):
    status: str
    is_connected: bool
    is_streaming: bool
    focus_percentage: float
    alpha_beta_ratio: float

class ConnectRequest(BaseModel):
    mac_address: Optional[str] = None
    serial_port: Optional[str] = None

def calculate_alpha_beta_ratio(data, eeg_channels, sampling_rate):
    """Calculate alpha/beta ratio from EEG data."""
    try:
        if data.shape[1] == 0:
            return None
        
        bands = {}
        for ch in eeg_channels:
            # Detrend and filter
            channel_data = data[ch].copy()
            DataFilter.detrend(channel_data, AggOperations.MEAN.value)
            DataFilter.perform_bandpass(
                channel_data, sampling_rate, 1.0, 50.0, 4, 
                FilterTypes.BUTTERWORTH.value, 0
            )
            
            # Calculate PSD
            psd = DataFilter.get_psd_welch(
                channel_data, nfft=256, overlap=128, 
                sampling_rate=sampling_rate, window=0
            )
            
            # Get band powers
            bands[ch] = {
                "alpha": DataFilter.get_band_power(psd, 8.0, 13.0),
                "beta": DataFilter.get_band_power(psd, 13.0, 30.0),
            }
        
        # Get AF7 and AF8 channels (typically indices 1 and 2)
        if len(eeg_channels) >= 3:
            AF7 = eeg_channels[1] if len(eeg_channels) > 1 else eeg_channels[0]
            AF8 = eeg_channels[2] if len(eeg_channels) > 2 else eeg_channels[0]
        else:
            AF7 = eeg_channels[0]
            AF8 = eeg_channels[0] if len(eeg_channels) > 1 else eeg_channels[0]
        
        # Calculate total alpha and beta
        total_alpha = bands[AF7]["alpha"] + bands[AF8]["alpha"]
        total_beta = bands[AF7]["beta"] + bands[AF8]["beta"]
        
        # Calculate ratio
        if total_beta < 1e-6:
            return None
        
        ratio = total_alpha / total_beta
        return ratio
    
    except Exception as e:
        logger.error(f"Error calculating alpha/beta ratio: {e}")
        return None

def alpha_beta_ratio_to_focus_percentage(ratio):
    """
    Convert alpha/beta ratio to focus percentage (0-100%).
    
    Typical alpha/beta ratios:
    - Very relaxed/meditative: 2.0-4.0+
    - Normal relaxed: 1.0-2.0
    - Focused/alert: 0.5-1.0
    - Very focused/stressed: 0.0-0.5
    
    We'll map this to 0-100% where higher ratio = more focused.
    Actually, for attention/focus, lower alpha/beta typically means more focused.
    So we'll invert: lower ratio = higher focus percentage.
    """
    if ratio is None:
        return 0.0
    
    # Normalize ratio to 0-100%
    # Map ratio range [0.2, 3.0] to [100%, 0%] (inverted)
    min_ratio = 0.2
    max_ratio = 3.0
    
    # Clamp ratio
    ratio = max(min_ratio, min(max_ratio, ratio))
    
    # Invert: lower ratio = higher focus
    normalized = 1.0 - ((ratio - min_ratio) / (max_ratio - min_ratio))
    focus_percentage = normalized * 100.0
    
    # Clamp to 0-100
    return max(0.0, min(100.0, focus_percentage))

def streaming_worker():
    """Background thread that continuously reads EEG data and calculates focus."""
    logger.info("Streaming worker started")
    
    while device_state.is_streaming and device_state.is_connected:
        try:
            if device_state.board is None:
                time.sleep(UPDATE_INTERVAL)
                continue
            
            # Get data for the window
            samples_needed = int(device_state.sampling_rate * WINDOW_SECONDS)
            data = device_state.board.get_current_board_data(samples_needed)
            
            if data.shape[1] < samples_needed:
                time.sleep(0.1)
                continue
            
            # Calculate alpha/beta ratio
            ratio = calculate_alpha_beta_ratio(
                data, 
                device_state.eeg_channels, 
                device_state.sampling_rate
            )
            
            if ratio is not None:
                device_state.alpha_beta_ratio = ratio
                device_state.current_focus_percentage = alpha_beta_ratio_to_focus_percentage(ratio)
                
                # Queue update for WebSocket broadcast
                try:
                    device_state.update_queue.put_nowait({
                        "focus_percentage": device_state.current_focus_percentage,
                        "alpha_beta_ratio": device_state.alpha_beta_ratio,
                        "timestamp": time.time()
                    })
                except queue.Full:
                    pass  # Skip if queue is full
            
            time.sleep(UPDATE_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in streaming worker: {e}")
            time.sleep(1.0)
    
    logger.info("Streaming worker stopped")

async def broadcast_to_clients(message: dict):
    """Broadcast focus data to all connected WebSocket clients."""
    if not device_state.websocket_clients:
        return
    
    formatted_message = {
        "focus_percentage": round(message["focus_percentage"], 2),
        "alpha_beta_ratio": round(message["alpha_beta_ratio"], 4),
        "timestamp": message["timestamp"]
    }
    
    disconnected_clients = []
    for client in device_state.websocket_clients:
        try:
            await client.send_json(formatted_message)
        except Exception as e:
            logger.error(f"Error sending to client: {e}")
            disconnected_clients.append(client)
    
    # Remove disconnected clients
    for client in disconnected_clients:
        if client in device_state.websocket_clients:
            device_state.websocket_clients.remove(client)

async def process_update_queue():
    """Background task to process updates from the streaming worker."""
    while True:
        try:
            # Get update from queue (non-blocking with timeout)
            try:
                message = device_state.update_queue.get(timeout=0.1)
                await broadcast_to_clients(message)
            except queue.Empty:
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error processing update queue: {e}")
            await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    """Start background task for processing updates."""
    asyncio.create_task(process_update_queue())

# REST API Endpoints

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "message": "Muse 2 Focus Tracker API",
        "version": "1.0.0",
        "endpoints": {
            "GET /status": "Get device connection status",
            "POST /connect": "Connect to Muse 2 device",
            "POST /disconnect": "Disconnect from device",
            "GET /focus": "Get current focus percentage",
            "WS /ws": "WebSocket for live focus updates"
        }
    }

@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get current device connection status."""
    return StatusResponse(
        status="connected" if device_state.is_connected else "disconnected",
        is_connected=device_state.is_connected,
        is_streaming=device_state.is_streaming,
        focus_percentage=device_state.current_focus_percentage,
        alpha_beta_ratio=device_state.alpha_beta_ratio
    )

@app.post("/connect")
async def connect_device(request: ConnectRequest):
    """Connect to Muse 2 device."""
    if device_state.is_connected:
        return {
            "message": "Device already connected",
            "status": "connected"
        }
    
    try:
        params = BrainFlowInputParams()
        
        if request.mac_address:
            params.mac_address = request.mac_address
            logger.info(f"Connecting via MAC address: {request.mac_address}")
        elif request.serial_port:
            params.serial_port = request.serial_port
            logger.info(f"Connecting via serial port: {request.serial_port}")
        
        params.timeout = 15
        
        board = BoardShim(BOARD_ID, params)
        logger.info("Preparing Muse 2 session...")
        board.prepare_session()
        board.start_stream()
        
        # Get channel info
        eeg_channels = BoardShim.get_eeg_channels(BOARD_ID)
        sampling_rate = BoardShim.get_sampling_rate(BOARD_ID)
        
        device_state.board = board
        device_state.is_connected = True
        device_state.eeg_channels = eeg_channels
        device_state.sampling_rate = sampling_rate
        
        # Start streaming
        device_state.is_streaming = True
        device_state.streaming_thread = threading.Thread(
            target=streaming_worker, 
            daemon=True
        )
        device_state.streaming_thread.start()
        
        logger.info("Muse 2 connected and streaming started!")
        
        return {
            "message": "Device connected successfully",
            "status": "connected",
            "device": "Muse 2",
            "sampling_rate": sampling_rate,
            "channels": len(eeg_channels)
        }
    
    except BrainFlowError as e:
        logger.error(f"BrainFlow error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to device: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Connection error: {str(e)}"
        )

@app.post("/disconnect")
async def disconnect_device():
    """Disconnect from Muse 2 device."""
    if not device_state.is_connected:
        return {
            "message": "Device not connected",
            "status": "disconnected"
        }
    
    try:
        # Stop streaming
        device_state.is_streaming = False
        
        # Wait for streaming thread to finish
        if device_state.streaming_thread and device_state.streaming_thread.is_alive():
            device_state.streaming_thread.join(timeout=2.0)
        
        # Stop and release board
        if device_state.board:
            try:
                device_state.board.stop_stream()
                device_state.board.release_session()
            except Exception as e:
                logger.error(f"Error releasing board: {e}")
        
        device_state.board = None
        device_state.is_connected = False
        device_state.current_focus_percentage = 0.0
        device_state.alpha_beta_ratio = 0.0
        
        logger.info("Device disconnected")
        
        return {
            "message": "Device disconnected successfully",
            "status": "disconnected"
        }
    
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Disconnect error: {str(e)}"
        )

@app.get("/focus")
async def get_focus():
    """Get current focus percentage."""
    return {
        "focus_percentage": round(device_state.current_focus_percentage, 2),
        "alpha_beta_ratio": round(device_state.alpha_beta_ratio, 4),
        "is_connected": device_state.is_connected,
        "is_streaming": device_state.is_streaming,
        "timestamp": time.time()
    }

# WebSocket endpoint for live updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live focus percentage updates."""
    await websocket.accept()
    device_state.websocket_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(device_state.websocket_clients)}")
    
    try:
        # Send initial data
        await websocket.send_json({
            "focus_percentage": round(device_state.current_focus_percentage, 2),
            "alpha_beta_ratio": round(device_state.alpha_beta_ratio, 4),
            "is_connected": device_state.is_connected,
            "timestamp": time.time()
        })
        
        # Keep connection alive and handle disconnects
        while True:
            try:
                # Wait for any message (ping/pong or disconnect)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo back or handle ping
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send periodic keepalive
                await websocket.send_json({
                    "type": "keepalive",
                    "timestamp": time.time()
                })
            except WebSocketDisconnect:
                break
    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in device_state.websocket_clients:
            device_state.websocket_clients.remove(websocket)
        logger.info(f"WebSocket client removed. Total clients: {len(device_state.websocket_clients)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown."""
    if device_state.is_connected:
        device_state.is_streaming = False
        if device_state.board:
            try:
                device_state.board.stop_stream()
                device_state.board.release_session()
            except:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

