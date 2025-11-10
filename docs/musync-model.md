# MUSYNC Model Diagram

Mermaid source and PNG/SVG export for the MUSYNC (Music Utilizing SYNchronized Cognitive feedback) model.

```mermaid
flowchart LR

  EEG[Focus Score<br/>(0-100, 1 Hz)]
  PROF[Profile<br/>(Questionnaire prefs)]
  BOUNDS[Safety Bounds<br/>(amp, tempo, density)]

  subgraph MUSYNC[MUSYNC Model]
    POL[RL Policy<br/>(exploit / explore)]
    ACT[Audio Params<br/>(density, tempo, layers, transitions)]
    GEN[Audio Generator<br/>(motifs, mixing, crossfade)]
  end

  PLAY[Playback<br/>(AudioWorklet, volume, skip)]
  RWD[Reward\n(Î” focus, stability)]

  EEG --> POL
  PROF --> POL
  BOUNDS --> POL
  POL --> ACT --> GEN --> PLAY
  EEG --> RWD --> POL

  subgraph Notes[Notes]
    N1[Profile biases policy toward user comfort]
    N2[Safety bounds cap changes and amplitude]
    N3[Explore when focus dips; keep when stable/rising]
  end
```

Exports
- Source: `docs/musync-model.mmd`
- Use app/frontend scripts: `npm run diagram:musync` (PNG) or `npm run diagram:musync:svg` (SVG)



