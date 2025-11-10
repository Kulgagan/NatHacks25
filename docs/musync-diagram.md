# MUSYNC Diagrams

This page contains the end-to-end pipeline and the runtime sequence for the app.

```mermaid
%% Pipeline (flowchart)
flowchart TD
  A[User Opens App] --> B[Connect & Permissions\nMuse 2 + Audio]
  B --> C[Calibration\nRelax → Task → Midpoint]
  C --> D[EEG Ingest & Features\nFilter + Artifact Gate + Bands]
  D --> E[Cognitive State\nAlpha/Beta → Focus %\nSmoothing]
  E --> F[Policy & Feedback\nKeep + Explore + Transition\nAdjust params]
  F --> G[Generation & Mixing\nMotif/Params + Crossfade]
  G --> H[Transport\nWebSocket PCM chunks]
  H --> I[Playback\nAudioWorklet + Volume + Skip]
  I -->|Focus updates (0-100)| E
  I --> J[UI & Controls\nDashboard, Calibration, Quiz]
  J --> F

  subgraph Personalization
    Q[Questionnaire\nProfile + Overrides] --> F
  end

  subgraph Safety & Telemetry
    S1[Latency guards + Underruns] --> H
    S2[Fade/flush on disconnect] --> I
    S3[Errors & metrics] --> J
  end
```

```mermaid
%% Runtime (sequence)
sequenceDiagram
  autonumber
  participant User
  participant UI as Frontend UI
  participant WS as WS Server (Audio)
  participant Worklet as AudioWorklet (PCM Player)

  User->>UI: Start Session
  UI->>UI: Init AudioContext + load worklet
  UI->>WS: Open WebSocket
  UI->>WS: send {focus, volume, profile}
  WS-->>UI: Binary PCM chunks
  UI->>Worklet: postMessage({chunk})
  Worklet->>Worklet: Schedule, cap amp, crossfade
  Note over UI,Worklet: Continuous low-latency playback

  loop ~750ms
    UI->>WS: send {focus}
  end

  User->>UI: Skip / Volume / Pause
  UI->>WS: {skip|volume}

  alt Disconnect/Error
    WS--x UI: onclose/onerror
    UI->>Worklet: fade + flush
    UI->>UI: Close WS, clear timers
  end

  opt Recalibrate
    User->>UI: Start relax/task
    UI->>UI: Measure + Update midpoint
    UI->>WS: Focus reflects new baseline
  end
```

Exports
- Source files: `docs/musync-flow.mmd`, `docs/musync-sequence.mmd`.
- To export PNG/SVG, use the scripts in `app/frontend/package.json` (see below) or one-off `npx @mermaid-js/mermaid-cli` commands.

