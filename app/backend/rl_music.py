
import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

import numpy as np

SAMPLE_RATE = 48000
CHUNK_SEC = 0.25  # 250 ms chunks to keep latency low
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SEC)

# -------------------------
# Simple epsilon-greedy bandit over "genres"
# -------------------------

GENRES = ["ambient", "lofi", "piano", "classicalish", "beats"]

@dataclass
class BanditPolicy:
    epsilon: float = 0.15
    values: Dict[str, float] = field(default_factory=lambda: {g: 0.0 for g in GENRES})
    counts: Dict[str, int] = field(default_factory=lambda: {g: 0 for g in GENRES})
    last_genre: str = "ambient"

    def select(self) -> str:
        import random
        if random.random() < self.epsilon:
            self.last_genre = random.choice(GENRES)
        else:
            self.last_genre = max(self.values, key=self.values.get)
        return self.last_genre

    def update(self, genre: str, reward: float):
        # incremental mean update
        c = self.counts[genre] + 1
        v = self.values[genre] + (reward - self.values[genre]) / c
        self.values[genre] = v
        self.counts[genre] = c


# -------------------------
# Procedural audio synth blocks
# -------------------------

def envelope_attack_decay(length: int, sr: int, attack: float = 0.02, decay: float = 0.2) -> np.ndarray:
    """Very simple A-D envelope clipped to buffer length."""
    a_s = max(1, int(sr * attack))
    d_s = max(1, int(sr * decay))
    env = np.ones(length, dtype=np.float32)
    a = np.linspace(0.0, 1.0, min(a_s, length), dtype=np.float32)
    env[:a.size] = a
    if length > a.size:
        d = np.linspace(1.0, 0.8, min(d_s, length - a.size), dtype=np.float32)
        env[a.size:a.size + d.size] = d
    return env

@dataclass
class Osc:
    freq: float
    phase: float = 0.0

    def render(self, n: int, sr: int, wave: str = "sine") -> np.ndarray:
        t = (np.arange(n, dtype=np.float32) + 0.0) / sr
        # phase increment
        inc = 2.0 * np.pi * self.freq / sr
        ph = self.phase + inc * np.arange(n, dtype=np.float32)
        if wave == "sine":
            x = np.sin(ph)
        elif wave == "square":
            x = np.sign(np.sin(ph)).astype(np.float32)
        elif wave == "saw":
            x = 2.0 * (ph / (2*np.pi) - np.floor(0.5 + ph / (2*np.pi))).astype(np.float32)
        else:
            x = np.sin(ph)
        self.phase = (self.phase + inc * n) % (2*np.pi)
        return x.astype(np.float32)

def lowpass(x: np.ndarray, cutoff_hz: float, sr: int) -> np.ndarray:
    # one-pole low-pass
    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    y = np.zeros_like(x, dtype=np.float32)
    for i in range(len(x)):
        y[i] = y[i-1] + alpha * (x[i] - y[i-1]) if i > 0 else alpha * x[i]
    return y

@dataclass
class MusicSynth:
    sr: int = SAMPLE_RATE
    bpm: float = 84.0
    t: float = 0.0  # time cursor in seconds
    # persistent oscillators to maintain phase continuity
    voices: Dict[str, Osc] = field(default_factory=dict)
    current_chord_idx: int = 0
    last_genre: str = "ambient"
    crossfade_tail: Optional[np.ndarray] = None

    def _ensure_voice(self, key: str, freq: float, wave: str="sine") -> np.ndarray:
        if key not in self.voices:
            self.voices[key] = Osc(freq=freq, phase=0.0)
        return self.voices[key].render(CHUNK_SAMPLES, self.sr, wave)

    def _chord_freqs(self, root_hz: float, chord: Tuple[int, int, int] = (0,4,7)) -> List[float]:
        # major triad by default
        semis = np.array(chord, dtype=np.float32)
        return list(root_hz * (2.0 ** (semis/12.0)))

    def _beats_layer(self, strength: float=1.0) -> np.ndarray:
        # simple kick-snare-hat at current bpm
        n = CHUNK_SAMPLES
        sec_per_beat = 60.0 / self.bpm
        samples_per_beat = int(self.sr * sec_per_beat)
        pos = int((self.t * self.sr) % samples_per_beat)
        x = np.zeros(n, dtype=np.float32)

        for i in range(n):
            beat_phase = ((pos + i) % samples_per_beat) / samples_per_beat
            if beat_phase < 0.02:  # kick on beat
                freq = 60 + 80 * (1 - beat_phase/0.02)
                x[i] += 0.8 * math.sin(2*np.pi*freq*i/self.sr)
            if 0.5 - 0.01 < beat_phase < 0.5 + 0.01:  # snare on 2
                x[i] += 0.3 * (np.random.rand() * 2 - 1)
            # hi-hat sixteenths
            if (beat_phase*16) % 1.0 < 0.02:
                x[i] += 0.05 * (np.random.rand() * 2 - 1)
        x = lowpass(x, 4000, self.sr)
        return x * strength

    def render_chunk(self, genre: str, focus: float) -> np.ndarray:
        """Generate a mono float32 PCM chunk in [-1,1]"""
        n = CHUNK_SAMPLES
        base = np.zeros(n, dtype=np.float32)

        # ambient pad
        if genre == "ambient":
            base += 0.4*self._ensure_voice("amb1", 110, "sine")
            base += 0.3*self._ensure_voice("amb2", 220, "sine")
            base += 0.2*self._ensure_voice("amb3", 330, "sine")
            base = lowpass(base, 1500, self.sr)

        # lo-fi
        elif genre == "lofi":
            base += 0.5*self._ensure_voice("lofi1", 220, "saw")
            base += 0.2*self._ensure_voice("lofi2", 440, "sine")
            noise = (np.random.rand(n).astype(np.float32)*2-1) * 0.03
            base = lowpass(base, 2000, self.sr) + noise

        # piano-ish arpeggio
        elif genre == "piano":
            chord_prog = [(0,4,7), (9,0,4), (7,11,2), (5,9,0)]  # I-vi-V-iv style (mod 12)
            if int(self.t / (4*60.0/self.bpm)) % len(chord_prog) != self.current_chord_idx:
                self.current_chord_idx = int(self.t / (4*60.0/self.bpm)) % len(chord_prog)
            chord = chord_prog[self.current_chord_idx]
            root = 261.63  # C4
            freqs = self._chord_freqs(root, chord)
            for i, f in enumerate(freqs):
                base += (0.3/(i+1))*self._ensure_voice(f"pn{i}", f, "sine")
            base *= envelope_attack_decay(n, self.sr, 0.005, 0.1)

        # classical-ish strings pad
        elif genre == "classicalish":
            base += 0.3*self._ensure_voice("cl1", 196, "sine")
            base += 0.3*self._ensure_voice("cl2", 293.66, "sine")
            base += 0.2*self._ensure_voice("cl3", 329.63, "sine")
            base = lowpass(base, 1800, self.sr)

        # beats
        elif genre == "beats":
            base += self._beats_layer(0.8)
            base += 0.2*self._ensure_voice("bass", 55, "sine")

        # gentle focus-adaptive gain and brightness
        target_gain = 0.5 + 0.5*(focus/100.0)
        base = np.tanh(base * target_gain).astype(np.float32)

        # crossfade if genre changed
        if self.last_genre != genre:
            if self.crossfade_tail is None:
                self.crossfade_tail = base.copy()
            # 100 ms crossfade
            cf = int(0.1 * self.sr)
            fade = np.linspace(0,1,cf).astype(np.float32)
            base[:cf] = (1-fade)*self.crossfade_tail[:cf] + fade*base[:cf]

        self.last_genre = genre
        self.t += n / self.sr
        self.crossfade_tail = base[-int(0.1*self.sr):].copy()
        return base

@dataclass
class MusicSession:
    policy: BanditPolicy = field(default_factory=BanditPolicy)
    synth: MusicSynth = field(default_factory=MusicSynth)
    volume: float = 0.8
    last_focus: float = 0.0
    last_focus_time: float = field(default_factory=lambda: time.time())

    def set_focus(self, val: float):
        self.last_focus = float(np.clip(val, 0.0, 100.0))
        self.last_focus_time = time.time()

    def skip(self):
        # small nudge to explore next genre
        self.policy.epsilon = min(0.9, self.policy.epsilon + 0.1)

    def next_chunk(self) -> bytes:
        # reward: positive if focus trending up in last few seconds
        reward = (self.last_focus - 50.0) / 50.0  # normalize around 0
        # choose genre
        if reward > 0.05:
            # keep current genre if it's performing well
            genre = self.policy.last_genre
        else:
            genre = self.policy.select()
        # update policy
        self.policy.update(genre, reward)
        # render audio
        pcm = self.synth.render_chunk(genre, self.last_focus) * self.volume
        # float32 little-endian binary
        return pcm.astype(np.float32).tobytes()

