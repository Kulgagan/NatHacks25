import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import Visualizer from "@/components/Visualizer";
import { Slider } from "@/components/ui/slider";
import { Pause, Play, SkipForward, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const Session = () => {
  // UI state
  const [playing, setPlaying] = useState<boolean>(false); // sound OFF by default
  const [volume, setVolume] = useState<number[]>([70]);   // slider expects [number]
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

  // --- Keep dashboard metrics up-to-date (focus %, alpha/beta, connection)
  useEffect(() => {
    const tick = async () => {
      try {
        const s = await api.getStatus();
        setIsConnected(s.is_connected);
        setIsStreaming(s.is_streaming);
        if (typeof s.focus_percentage === "number") setFocusLevel(Math.max(0, Math.min(100, s.focus_percentage)));
        if (typeof s.alpha_beta_ratio === "number") setAlphaBetaRatio(s.alpha_beta_ratio);
      } catch (err) {
        // keep quiet but you can log if needed
      }
    };

    // first fetch immediately, then poll
    tick();
    statusTimerRef.current = window.setInterval(tick, 1000) as unknown as number;
    return () => {
      if (statusTimerRef.current) {
        window.clearInterval(statusTimerRef.current);
        statusTimerRef.current = null;
      }
    };
  }, []);

  // --- Start / Stop adaptive music when "playing" changes
  useEffect(() => {
    const startMusic = async () => {
      try {
        // AudioContext + Worklet
        // @ts-ignore vendor-prefixed fallback is OK at runtime
        const ACtx = window.AudioContext || window.webkitAudioContext;
        const ctx: AudioContext = new ACtx();
        audioCtxRef.current = ctx;

        await ctx.audioWorklet.addModule("/worklets/pcm-player.js");
        const node = new AudioWorkletNode(ctx, "pcm-player", { numberOfOutputs: 1 });
        node.connect(ctx.destination);
        workletRef.current = node;

        // Music WebSocket (binary chunks of Float32 PCM)
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
            const f32 = new Float32Array(ev.data);
            // forward to the worklet; transfer the buffer to avoid copies
            workletRef.current?.port.postMessage({ type: "chunk", payload: f32 }, [f32.buffer]);
          }
        };

        ws.onerror = () => {
          toast.error("Music connection error.");
        };

        ws.onclose = () => {
          // no-op; cleanup handled below
        };

        // Periodically push latest focus to the RL agent
        focusPushTimerRef.current = window.setInterval(() => {
          try {
            musicWsRef.current?.send(JSON.stringify({ type: "focus", value: focusLevel }));
          } catch {}
        }, 750) as unknown as number;
      } catch (err) {
        toast.error("Failed to start adaptive music.");
        // ensure we flip the toggle off if startup fails
        setPlaying(false);
      }
    };

    const stopMusic = () => {
      try {
        musicWsRef.current?.send(JSON.stringify({ type: "stop" }));
      } catch {}
      try {
        musicWsRef.current?.close();
      } catch {}
      musicWsRef.current = null;

      if (focusPushTimerRef.current) {
        window.clearInterval(focusPushTimerRef.current);
        focusPushTimerRef.current = null;
      }

      try {
        workletRef.current?.disconnect();
      } catch {}
      workletRef.current = null;

      try {
        audioCtxRef.current?.close();
      } catch {}
      audioCtxRef.current = null;
    };

    if (playing) {
      startMusic();
    } else {
      stopMusic();
    }

    return () => {
      stopMusic();
    };
    // Also react to volume changes so initial volume is pushed on first play.
    // focusLevel is pushed via timer; we don't need to restart on every change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  // --- UI handlers
  const togglePlay = async () => {
    // Most browsers require a user gesture to start audio
    setPlaying((p) => !p);
  };

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-card to-muted flex flex-col relative overflow-hidden">
      {/* Animated background responding to focus */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full blur-3xl transition-all duration-1000"
          style={{
            // soft green/teal when focused; warmer when low
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

            <Button variant="outline" size="icon" onClick={skipGenre} aria-label="Skip to a new texture">
              <SkipForward className="w-5 h-5" />
            </Button>

            <div className="flex items-center gap-2 ml-2">
              <Volume2 className="w-5 h-5 text-muted-foreground" />
              <div className="w-40">
                <Slider
                  value={volume}
                  max={100}
                  step={1}
                  onValueChange={handleVolumeChange}
                  aria-label="Volume"
                />
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
            <p className="text-sm text-muted-foreground mt-1">
              α/β ratio: {alphaBetaRatio.toFixed(2)}
            </p>
            <div className="mt-6">
              {/* Your existing visualizer expects focusLevel; keep it plugged in */}
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
              <li>• Use Skip to nudge it to a new texture</li>
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Session;