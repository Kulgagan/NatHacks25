// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Types
export interface StatusResponse {
  status: string;
  is_connected: boolean;
  is_streaming: boolean;
  focus_percentage: number;
  alpha_beta_ratio: number;
}

export interface ConnectRequest {
  mac_address?: string;
  serial_port?: string;
}

export interface FocusResponse {
  focus_percentage: number;
  alpha_beta_ratio: number;
  is_connected: boolean;
  is_streaming: boolean;
  timestamp: number;
}

export interface CalibrationStatus {
  phase: 'relax' | 'task' | null;
  elapsed: number;
  counts: { relax: number; task: number };
  midpoint: number | null;
}

// API Functions
export const api = {
  // Get device status
  async getStatus(): Promise<StatusResponse> {
    const response = await fetch(`${API_BASE_URL}/status`);
    if (!response.ok) {
      throw new Error('Failed to get status');
    }
    return response.json();
  },

  // Connect to device
  async connect(request?: ConnectRequest): Promise<{ message: string; status: string }> {
    const response = await fetch(`${API_BASE_URL}/connect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request || {}),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to connect');
    }
    return response.json();
  },

  // Disconnect from device
  async disconnect(): Promise<{ message: string; status: string }> {
    const response = await fetch(`${API_BASE_URL}/disconnect`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to disconnect');
    }
    return response.json();
  },

  // Get current focus
  async getFocus(): Promise<FocusResponse> {
    const response = await fetch(`${API_BASE_URL}/focus`);
    if (!response.ok) {
      throw new Error('Failed to get focus');
    }
    return response.json();
  },

  // WebSocket URL
  getWebSocketUrl(): string {
    const wsProtocol = API_BASE_URL.startsWith('https') ? 'wss' : 'ws';
    const wsHost = API_BASE_URL.replace(/^https?:\/\//, '');
    return `${wsProtocol}://${wsHost}/ws`;
  },

  // Music WebSocket URL
  getMusicWebSocketUrl(): string {
    const wsProtocol = API_BASE_URL.startsWith('https') ? 'wss' : 'ws';
    const wsHost = API_BASE_URL.replace(/^https?:\/\//, '');
    return `${wsProtocol}://${wsHost}/ws/music`;
  },

  // Calibration controls
  async startCalibration(phase: 'relax' | 'task'): Promise<{ status: string; phase: string }> {
    const res = await fetch(`${API_BASE_URL}/calibration/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase }),
    });
    if (!res.ok) throw new Error('Failed to start calibration');
    return res.json();
  },
  async stopCalibration(phase: 'relax' | 'task'): Promise<{ status: string; phase: string; stats: any }> {
    const res = await fetch(`${API_BASE_URL}/calibration/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase }),
    });
    if (!res.ok) throw new Error('Failed to stop calibration');
    return res.json();
  },
  async commitCalibration(): Promise<{ status: string; midpoint: number; relax_mean: number; task_mean: number; counts: {relax:number; task:number} }> {
    const res = await fetch(`${API_BASE_URL}/calibration/commit`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to commit calibration');
    return res.json();
  },
  async getCalibrationStatus(): Promise<CalibrationStatus> {
    const res = await fetch(`${API_BASE_URL}/calibration/status`);
    if (!res.ok) throw new Error('Failed to get calibration status');
    return res.json();
  },
}
