# app/backend/rl_music.py
# Ultra-slow ambient engine (numpy-only) with rare, crossfaded texture changes.
# Mono Float32 @ 48kHz, 0.25s chunks. No clicky notes; no drums; no hiss.

import time, threading, queue, logging, math
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import numpy as np

log = logging.getLogger("rl_music")
log.setLevel(logging.INFO)

# ===== Stream format =====
OUT_SR = 48_000
CHUNK_SEC = 0.25
CHUNK_SAMPLES = int(OUT_SR * CHUNK_SEC)

# ===== Textures (very soft sines w/ subtle harmonics) =====
# name, vibrato semitones, detune cents, brightness [0..1]
TEXTURE_MODES = [
    ("warm_pad",  0.02,  6.0, 0.10),
    ("stringy",   0.015, 8.0, 0.14),
    ("glassy",    0.010, 12.0, 0.18),
]

# ===== RL (very conservative) =====
RL_EPSILON = 0.06     # small exploration chance
RL_DELAY_BARS = 8     # wait after a change (let the fade settle)
RL_EVAL_BARS  = 8     # average focus over this many bars
RL_UPDATE_PROB = 0.33 # sparse updates

def _hz(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))

def _softclip(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    return np.tanh(x * drive, dtype=np.float32)

class SmoothParam:
    def __init__(self, initial: float, tau_s: float, sr: int):
        self.value = float(initial)
        self.alpha = math.exp(-1.0 / max(1, int(tau_s * sr)))
    def step(self, target: float, n: int) -> float:
        self.value = self.value * (self.alpha ** n) + target * (1 - (self.alpha ** n))
        return self.value

class OnePoleLPF:
    def __init__(self, sr: int, cutoff_hz: float):
        rc = 1.0 / (2.0 * math.pi * max(10.0, cutoff_hz))
        self.a = math.exp(-1.0 / (rc * sr))
        self.y = 0.0
    def process(self, x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x, dtype=np.float32)
        a = self.a; y = float(self.y)
        xv = x.astype(np.float32, copy=False)
        for i in range(xv.shape[0]):
            y = a * y + (1.0 - a) * float(xv[i])
            out[i] = y
        self.y = y
        return out

class SineOsc:
    def __init__(self, sr: int):
        self.sr = sr
        self.phase = 0.0
    def render_inst(self, f_inst: np.ndarray) -> np.ndarray:
        inc = 2*np.pi * f_inst / self.sr
        ph = np.cumsum(inc, dtype=np.float32) + self.phase
        y = np.sin(ph, dtype=np.float32)
        self.phase = float(ph[-1] % (2*np.pi))
        return y

class HarmPad:
    """Detuned multi-sine pad with faint 2nd harmonic. Super gentle."""
    def __init__(self, sr: int):
        self.sr = sr
        self.vibr = 0.015
        self.detune_cents = 8.0
        self.bright = 0.12
        self._vib_phase = 0.0
    def set_mode_params(self, vibr: float, detune_cents: float, bright: float):
        self.vibr = float(vibr); self.detune_cents = float(detune_cents); self.bright = float(bright)
    def render(self, chord_midi: List[int], n: int) -> np.ndarray:
        if not chord_midi: return np.zeros(n, np.float32)
        out = np.zeros(n, np.float32)
        t = (np.arange(n, dtype=np.float32)) / self.sr
        vib = np.sin(2*np.pi*0.07*t + self._vib_phase).astype(np.float32) * self.vibr  # slower vibrato
        self._vib_phase += 2*np.pi*0.07*(n/self.sr)
        dets = np.array([-self.detune_cents, -self.detune_cents*0.5, 0.0,
                          +self.detune_cents*0.5, +self.detune_cents], dtype=np.float32)/100.0
        for i, note in enumerate(chord_midi[:4]):
            f0 = _hz(note)
            sem = vib + dets[i % len(dets)]*12.0
            f_inst = f0 * (2.0 ** (sem / 12.0))
            s1 = SineOsc(self.sr).render_inst(f_inst)
            if self.bright > 0.0:
                s2 = SineOsc(self.sr).render_inst(2.0*f_inst) * (0.20 * self.bright)
                out += (s1 + s2).astype(np.float32)
            else:
                out += s1
        out *= (0.16 / min(4, len(chord_midi)))
        return out.astype(np.float32)

class DroneOvertone:
    """
    Continuous, very soft overtone to avoid 'beeps':
      • 1.0 s attack, 4.0 s release envelope (per 'note' change, which is very rare)
      • low-pass at 600 Hz so it sits behind the pad
      • changes pitch only every many bars
    """
    def __init__(self, sr: int, cutoff=600.0):
        self.sr = sr
        self.attack = math.exp(-1.0 / (1.0 * sr))   # 1s
        self.release = math.exp(-1.0 / (4.0 * sr))  # 4s
        self.env = 0.0
        self.phase = 0.0
        self.freq = 0.0
        self.gain = 0.06
        self.lpf = OnePoleLPF(sr, cutoff_hz=cutoff)
    def set_freq(self, hz: float):
        # start a very gentle attack toward the new frequency
        self.freq = max(1.0, float(hz))
        # do not reset env to 0 -> prevents clicks; just let it glide
    def render(self, n: int) -> np.ndarray:
        if self.freq <= 0.0:
            return np.zeros(n, np.float32)
        ph = self.phase + 2*np.pi*self.freq*np.arange(n, dtype=np.float32)/self.sr
        s = np.sin(ph, dtype=np.float32)
        # apply slow AR envelope (per-sample)
        env = np.empty(n, np.float32); e = float(self.env)
        for i in range(n):
            # approach 1.0 slowly (attack), then multiply by slow release
            e = 1.0 - (1.0 - e)*self.attack
            env[i] = e
        self.env = e * (self.release ** n)
        y = self.lpf.process(s * env * self.gain)
        self.phase = float(ph[-1] % (2*np.pi))
        return y

@dataclass
class Bandit:
    epsilon: float = RL_EPSILON
    values: Dict[int, float] = field(default_factory=lambda: {i: 0.0 for i in range(len(TEXTURE_MODES))})
    counts: Dict[int, int] = field(default_factory=lambda: {i: 0 for i in range(len(TEXTURE_MODES))})
    def select(self) -> int:
        import random
        if random.random() < self.epsilon or all(c == 0 for c in self.counts.values()):
            return random.randrange(0, len(TEXTURE_MODES))
        return max(self.values, key=self.values.get)
    def update(self, idx: int, reward: float):
        c = self.counts[idx] + 1
        self.counts[idx] = c
        self.values[idx] = self.values[idx] + (reward - self.values[idx]) / c

class Engine:
    def __init__(self, sr: int = OUT_SR):
        self.sr = sr
        # Very slow tempo & grid
        self.tempo_bpm = 48  # ~5s per bar
        self.sp16 = self._sp16()
        self.bar_step16 = 0
        self.into = 0

        # Key & progression (slow rotation)
        self.key_root = 48  # C3
        self.scale = [0,2,3,5,7,10]
        self.chord_prog = self._make_progression()
        self.bars_per_chord = 8   # 8 bars per chord (~40s)
        self._bar_in_chord = 0

        # Sections (very long)
        self.section_len_bars = 64
        self.section_bar = 0
        self.global_bar = 0
        self.key_cycle = [48, 47, 50, 45, 48]  # C3 -> B2 -> D3 -> A2 -> C3

        # Pads for crossfade
        self.padA = HarmPad(sr)
        self.padB = HarmPad(sr)
        self.tex_idx = 0
        self.padA.set_mode_params(*TEXTURE_MODES[self.tex_idx][1:])
        self.padB.set_mode_params(*TEXTURE_MODES[self.tex_idx][1:])
        self.xf_active = False
        self.xf_pos = 0
        self.xf_total = int(20.0 * sr)  # 20s morphs

        # Drone overtone instead of arpeggio
        self.drone = DroneOvertone(sr, cutoff=600.0)
        self.drone_change_every_bars = 16  # update drone pitch only this often

        # Focus dynamics (master loudness only; no tempo changes)
        self.focus_s = SmoothParam(50.0, tau_s=2.0, sr=sr)
        self.master  = SmoothParam(0.22, tau_s=1.5, sr=sr)  # quieter overall

        # Texture hold
        self.hold_bars = 32
        self.bars_held = 0

        # Startup fade
        self.fade_in_left = int(2.0 * sr)

        # RL state (rare, delayed)
        self.bandit = Bandit()
        self.focus_bar_hist: List[float] = []
        self.eval_queue: List[Dict[str, int]] = []
        self._focus_avg = 50.0

    # grid helpers
    def _sp16(self): return int(self.sr * 60.0 / max(1, self.tempo_bpm) / 4.0)
    def _make_progression(self):
        degs = [0, 3, 4, 2]
        roots = [(self.key_root + self.scale[d%len(self.scale)]) for d in degs]
        return [[r, r+3, r+7, r+12] for r in roots]

    # focus -> master loudness (only; keep tempo fixed)
    def set_focus(self, f: float):
        f = float(np.clip(f, 0.0, 100.0))
        fs = self.focus_s.step(f, CHUNK_SAMPLES)
        self._focus_avg = 0.99 * self._focus_avg + 0.01 * fs
        target_master = 0.26 * (1.0 - 0.55*(fs/100.0))  # ~0.26 -> ~0.117
        self.master.step(target_master, CHUNK_SAMPLES)

        # If focus tanks and we held long enough, begin a *long* morph (still rare)
        if fs < 35.0 and not self.xf_active and self.bars_held >= self.hold_bars//2:
            self._begin_texture_change(longer=True)

    def _begin_texture_change(self, longer: bool = False):
        # RL decides the next texture (delayed reward later)
        next_idx = self.bandit.select()
        self.tex_idx = next_idx
        _, v, d, b = TEXTURE_MODES[self.tex_idx]
        self.padB.set_mode_params(v, d, b)
        self.xf_active = True
        self.xf_pos = 0
        self.xf_total = int((24.0 if longer else 20.0) * self.sr)  # 20–24s fade
        self.bars_held = 0
        self.eval_queue.append({"idx": self.tex_idx, "start_bar": self.global_bar})

    def _evaluate_bandit_if_due(self):
        if not self.eval_queue: return
        cur = self.global_bar
        keep = []
        for it in self.eval_queue:
            age = cur - it["start_bar"]
            if age < RL_DELAY_BARS + RL_EVAL_BARS:
                keep.append(it); continue
            a = it["start_bar"] + RL_DELAY_BARS
            b = a + RL_EVAL_BARS
            if b > len(self.focus_bar_hist):
                keep.append(it); continue
            window = self.focus_bar_hist[a:b]
            if not window:
                keep.append(it); continue
            avgf = float(np.mean(window))
            reward = ((avgf - 50.0) / 50.0) + 0.2 * np.sign(avgf - self._focus_avg)
            reward = float(np.clip(reward, -1.0, 1.0))
            if np.random.rand() < RL_UPDATE_PROB:
                self.bandit.update(it["idx"], reward)
        self.eval_queue = keep

    def _maybe_change_bar(self):
        self.bars_held += 1
        self.section_bar += 1
        self.global_bar += 1
        self.focus_bar_hist.append(float(self.focus_s.value))

        # gentle key modulation every long section
        if self.section_bar % self.section_len_bars == 0:
            k = (self.section_bar // self.section_len_bars) % len(self.key_cycle)
            self.key_root = self.key_cycle[k]
            self.chord_prog = self._make_progression()

        # change drone pitch every N bars (no attack pops)
        if self.global_bar % self.drone_change_every_bars == 0:
            # pick a stable degree within the current chord
            chord = self.chord_prog[0]
            drone_note = chord[0]  # root of chord
            self.drone.set_freq(_hz(drone_note))

        # evaluate RL if windows mature
        self._evaluate_bandit_if_due()

        # start a new texture when hold is up (rare)
        if self.bars_held >= self.hold_bars and not self.xf_active:
            self._begin_texture_change(longer=True)

    def render_chunk(self) -> np.ndarray:
        n = CHUNK_SAMPLES
        out = np.zeros(n, np.float32)
        remain = n; idx = 0

        while remain > 0:
            step_left = self.sp16 - self.into
            take = min(remain, step_left)

            # bar boundary (every 16 steps)
            if self.into == 0 and self.bar_step16 % 16 == 0:
                # advance bar-in-chord; rotate only every N bars
                self._bar_in_chord = (self._bar_in_chord + 1) % max(1, self.bars_per_chord)
                if self._bar_in_chord == 0:
                    self.chord_prog = self.chord_prog[1:] + self.chord_prog[:1]
                self._maybe_change_bar()

            chord = self.chord_prog[0]

            # Pad with long crossfade
            padA = HarmPad.render(self.padA, chord, take)
            if self.xf_active:
                padB = HarmPad.render(self.padB, chord, take)
                w_start = self.xf_pos / max(1, self.xf_total)
                w_end   = (self.xf_pos + take) / max(1, self.xf_total)
                w = np.linspace(w_start, w_end, take, dtype=np.float32)
                pad = (1.0 - w) * padA + w * padB
                self.xf_pos += take
                if self.xf_pos >= self.xf_total:
                    self.padA, self.padB = self.padB, self.padA
                    self.padB.set_mode_params(*TEXTURE_MODES[self.tex_idx][1:])
                    self.xf_active = False
                    self.xf_pos = 0
            else:
                pad = padA

            # Very soft drone
            drone = self.drone.render(take)

            out[idx:idx+take] += (pad * 0.95 + drone * 1.0).astype(np.float32)

            self.into += take
            if self.into >= self.sp16:
                self.into = 0
                self.bar_step16 = (self.bar_step16 + 1) % 16

            idx += take; remain -= take

        # Master loudness (focus-ducked) + gentle limiter
        out = _softclip(out * float(self.master.value), drive=1.0)

        # startup fade
        if self.fade_in_left > 0:
            k = min(n, self.fade_in_left)
            out[:k] *= np.linspace(0.0, 1.0, k, dtype=np.float32)
            self.fade_in_left -= k

        return out.astype(np.float32)

# ===== Session (short queue, self-healing) =====
@dataclass
class MusicSession:
    volume: float = 0.8
    last_focus: float = 0.0
    _q: "queue.Queue[bytes]" = field(default_factory=lambda: queue.Queue(maxsize=16))
    _stop: threading.Event = field(default_factory=threading.Event)
    _gen_thread: Optional[threading.Thread] = None
    _engine: Engine = field(default_factory=lambda: Engine(OUT_SR))

    def __post_init__(self):
        self._start_thread()

    def set_focus(self, val: float):
        self.last_focus = float(np.clip(val, 0.0, 100.0))
        self._ensure_thread()

    def set_volume(self, v: float):
        self.volume = float(np.clip(v, 0.0, 1.0))

    def skip(self):
        self._engine._begin_texture_change(longer=True)
        self._ensure_thread()

    def next_chunk(self) -> bytes:
        self._ensure_thread()
        try:
            data = self._q.get(timeout=1.0)
        except queue.Empty:
            return (np.zeros(CHUNK_SAMPLES, dtype=np.float32) * self.volume).tobytes()
        if self.volume != 1.0:
            arr = np.frombuffer(data, dtype=np.float32).copy()
            arr *= np.float32(self.volume)
            return arr.tobytes()
        return data

    def _start_thread(self):
        self._stop.clear()
        self._gen_thread = threading.Thread(target=self._loop, daemon=True)
        self._gen_thread.start()

    def _ensure_thread(self):
        t = self._gen_thread
        if t is None or not t.is_alive():
            self._start_thread()

    def _loop(self):
        log.info("Ambient generator thread starting.")
        try:
            while not self._stop.is_set():
                if self._q.qsize() > 8:
                    time.sleep(0.02)
                    continue
                self._engine.set_focus(self.last_focus)
                chunk = self._engine.render_chunk().astype(np.float32)
                try:
                    self._q.put_nowait(chunk.tobytes())
                except queue.Full:
                    time.sleep(0.005)
        except Exception as e:
            log.exception("Generator crashed: %s", e)
        finally:
            log.info("Ambient generator thread ended.")

    def close(self):
        self._stop.set()
        try:
            if self._gen_thread and self._gen_thread.is_alive():
                self._gen_thread.join(timeout=1.0)
        finally:
            self._gen_thread = None
