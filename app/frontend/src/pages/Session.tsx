import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import Visualizer from "@/components/Visualizer";
import { Slider } from "@/components/ui/slider";
import { Pause, Play, SkipForward, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const Session = () => {
  // UI state
  const [playing, setPlaying] = useState<boolean>(false);
  const [volume, setVolume] = useState<number[]>([70]);
  const [focusLevel, setFocusLevel] = useState<number>(0);
  const [alphaBetaRatio, setAlphaBetaRatio] = useState<number>(0);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);

  // Audio + WS refs
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const musicWsRef = useRef<WebSocket | null>(null);

  // timers
  const statusTimerRef = useRef<number | null>(null);
  const focusPushTimerRef = useRef<number | null>(null);

  // debug HUD
  const [audioReady, setAudioReady] = useState(false);
  const [workletLoaded, setWorkletLoaded] = useState(false);
  const [wsState, setWsState] = useState<"idle" | "open" | "error" | "closed">("idle");
  const [lastChunkBytes, setLastChunkBytes] = useState(0);
  const [lastChunkAmp, setLastChunkAmp] = useState(0);
  const [lastError, setLastError] = useState<string>("");

  // Keep dashboard metrics fresh
  useEffect(() => {
    const tick = async () => {
      try {
        const s = await api.getStatus();
        setIsConnected(s.is_connected);
        setIsStreaming(s.is_streaming);
        if (typeof s.focus_percentage === "number") {
          setFocusLevel(Math.max(0, Math.min(100, s.focus_percentage)));
        }
        if (typeof s.alpha_beta_ratio === "number") setAlphaBetaRatio(s.alpha_beta_ratio);
      } catch {
        // ignore
      }
    };
    tick();
    statusTimerRef.current = window.setInterval(tick, 1000) as unknown as number;
    return () => {
      if (statusTimerRef.current) {
        window.clearInterval(statusTimerRef.current);
        statusTimerRef.current = null;
      }
    };
  }, []);

  // Start/stop adaptive music
  useEffect(() => {
    const startMusic = async () => {
    try {
      // AudioContext + Worklet
      // @ts-ignore
      const ACtx = (window as any).AudioContext || (window as any).webkitAudioContext;
      const ctx: AudioContext = new ACtx();
      audioCtxRef.current = ctx;
      await ctx.audioWorklet.addModule('/worklets/pcm-player.js');
      await ctx.resume();

      // Worklet -> Gain -> Destination
      const node = new AudioWorkletNode(ctx, 'pcm-player', { numberOfOutputs: 1 });
      workletRef.current = node;

      const gain = ctx.createGain();
      gain.gain.value = 1.0;
      node.connect(gain);
      gain.connect(ctx.destination);

      // helper to fade and teardown
      const fadeAndClose = async () => {
        try {
          // tell worklet to flush and fade
          node.port.postMessage({ type: 'flush' });
        } catch {}
        try {
          const now = ctx.currentTime;
          gain.gain.setValueAtTime(gain.gain.value, now);
          gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.2);
        } catch {}
        try { node.disconnect(); } catch {}
        try { gain.disconnect(); } catch {}
        try { await ctx.close(); } catch {}
        workletRef.current = null;
        audioCtxRef.current = null;
      };

      // WebSocket
      const ws = new WebSocket(api.getMusicWebSocketUrl());
      ws.binaryType = "arraybuffer";
      musicWsRef.current = ws;

      ws.onopen = () => {
        try {
          ws.send(JSON.stringify({ type: "focus", value: focusLevel }));
          ws.send(JSON.stringify({ type: "volume", value: (volume?.[0] ?? 70) / 100 }));
        } catch {}
      };

      ws.onmessage = (ev) => {
        if (ev.data instanceof ArrayBuffer) {
          // pass raw buffer; worklet copies & caps internally
          workletRef.current?.port.postMessage({ type: 'chunk', payload: ev.data }, [ev.data]);
        } else {
          // optional: handle text control messages
          // const msg = JSON.parse(ev.data);
        }
      };

      ws.onerror = () => {
        toast.error("Music connection error.");
      };

      ws.onclose = () => {
        // Immediate local stop when server disappears
        fadeAndClose();
        setPlaying(false);
        toast.info("Music connection closed.");
      };

      // push focus periodically
      focusPushTimerRef.current = window.setInterval(() => {
        try {
          musicWsRef.current?.send(JSON.stringify({ type: "focus", value: focusLevel }));
        } catch {}
      }, 750) as unknown as number;

      // ensure our teardown runs if the tab suspends or user navigates
      window.addEventListener('beforeunload', fadeAndClose);

      // store a ref to the local teardown so stopMusic can call it
      (node as any)._fadeAndClose = fadeAndClose;

    } catch (err) {
      toast.error("Failed to start adaptive music.");
      setPlaying(false);
      }
    };

    const stopMusic = () => {
    try { musicWsRef.current?.send(JSON.stringify({ type: "stop" })); } catch {}
    try { musicWsRef.current?.close(); } catch {}
    musicWsRef.current = null;

    if (focusPushTimerRef.current) {
      window.clearInterval(focusPushTimerRef.current);
      focusPushTimerRef.current = null;
    }

    try { workletRef.current?.port.postMessage({ type: 'flush' }); } catch {}
    try {
      // if we stored the local fade helper:
      const fadeAndClose = (workletRef.current as any)?._fadeAndClose;
      if (typeof fadeAndClose === 'function') fadeAndClose();
    } catch {}
    try { workletRef.current?.disconnect(); } catch {}
    workletRef.current = null;

    try { audioCtxRef.current?.close(); } catch {}
    audioCtxRef.current = null;

    window.removeEventListener('beforeunload', () => {});
    };


    if (playing) startMusic();
    else stopMusic();

    return () => stopMusic();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  // UI handlers
  const togglePlay = () => setPlaying((p) => !p);

  const handleVolumeChange = (v: number[]) => {
    setVolume(v);
    try {
      musicWsRef.current?.send(JSON.stringify({ type: "volume", value: v[0] / 100 }));
    } catch {}
  };

  const skipGenre = () => {
    try {
      musicWsRef.current?.send(JSON.stringify({ type: "skip" }));
    } catch {}
  };

  // Local test: push a 1s 440Hz tone into the worklet (bypasses the WS)
  const testTone = async () => {
    try {
      if (!audioCtxRef.current) {
        const ACtx: typeof AudioContext =
          (window as any).AudioContext || (window as any).webkitAudioContext;
        const ctx: AudioContext = new ACtx();
        audioCtxRef.current = ctx;
        await ctx.audioWorklet.addModule("/worklets/pcm-player.js");
        await ctx.resume();
        const node = new AudioWorkletNode(ctx, "pcm-player", { numberOfOutputs: 1 });
        node.connect(ctx.destination);
        workletRef.current = node;
        setAudioReady(true);
        setWorkletLoaded(true);
      }
      const ctx = audioCtxRef.current!;
      const n = Math.floor(ctx.sampleRate * 1.0);
      const buf = new Float32Array(n);
      for (let i = 0; i < n; i++) buf[i] = Math.sin(2 * Math.PI * 440 * (i / ctx.sampleRate)) * 0.2;
      workletRef.current?.port.postMessage({ type: "chunk", payload: buf.buffer }, [buf.buffer]);
      toast.success("Test tone sent");
    } catch (e: any) {
      setLastError(String(e?.message || e));
      toast.error("Test tone failed");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-card to-muted flex flex-col relative overflow-hidden">
      {/* Animated background responding to focus */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full blur-3xl transition-all duration-1000"
          style={{
            backgroundColor: `hsla(${focusLevel > 70 ? "185, 70%, 50%" : focusLevel > 40 ? "170, 60%, 55%" : "0, 70%, 60%"}, 0.15)`,
            transform: `scale(${0.8 + (focusLevel / 100) * 0.4})`,
          }}
        />
        <div
          className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full blur-3xl transition-all duration-1000"
          style={{
            backgroundColor: `hsla(${focusLevel > 70 ? "180, 70%, 55%" : focusLevel > 40 ? "160, 60%, 55%" : "20, 80%, 55%"}, 0.12)`,
            transform: `scale(${0.9 + (focusLevel / 100) * 0.3})`,
          }}
        />
      </div>

      <main className="relative z-10 container mx-auto max-w-5xl px-4 py-10">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold">Focus Session</h1>
            <p className="text-sm text-muted-foreground">
              {isConnected ? (isStreaming ? "Muse connected · streaming" : "Muse connected") : "Muse disconnected"}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              size="icon"
              variant={playing ? "secondary" : "default"}
              onClick={togglePlay}
              aria-label={playing ? "Pause adaptive music" : "Play adaptive music"}
            >
              {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            </Button>

            <div className="flex items-center gap-2 ml-2">
              <Volume2 className="w-5 h-5 text-muted-foreground" />
              <div className="w-40">
                <Slider value={volume} max={100} step={1} onValueChange={handleVolumeChange} aria-label="Volume" />
              </div>
            </div>
          </div>
        </header>
        {/* Focus visual + stats */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-2xl border bg-card p-6">
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-medium">Focus</h2>
              <span className="text-3xl font-semibold">{Math.round(focusLevel)}%</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">α/β ratio: {alphaBetaRatio.toFixed(2)}</p>
            <div className="mt-6">
              <Visualizer focusLevel={focusLevel} />
            </div>
            <p className="mt-4 text-muted-foreground text-sm">
              {playing ? "Music adapting to your focus level..." : "Paused"}
            </p>
          </div>

          <div className="rounded-2xl border bg-card p-6">
            <h2 className="text-lg font-medium mb-3">Adaptive Music</h2>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Infinite, seamless generation (low-latency streaming)</li>
              <li>• RL agent keeps what improves focus, explores when it dips</li>
            </ul>
          </div>
        </section>
        {/* Debug HUD */}
        <div className="mt-8 mb-6 rounded-xl border bg-card p-4 text-sm">
          <div className="font-medium mb-2">Audio Debug</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div>Audio ready: <span className="font-mono">{String(audioReady)}</span></div>
            <div>Worklet loaded: <span className="font-mono">{String(workletLoaded)}</span></div>
            <div>WS state: <span className="font-mono">{wsState}</span></div>
            <div>Last chunk: <span className="font-mono">{lastChunkBytes} bytes</span></div>
            <div>Max amp: <span className="font-mono">{lastChunkAmp.toFixed(5)}</span></div>
            <div className="col-span-2 md:col-span-4">
              {lastError && <span className="text-red-500">Error: {lastError}</span>}
            </div>
          </div>
          <div className="mt-3">
            <Button variant="outline" onClick={testTone}>Play 1s Test Tone</Button>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Session;
