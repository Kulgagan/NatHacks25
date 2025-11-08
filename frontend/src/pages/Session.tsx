import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Pause, Play, SkipForward, Volume2 } from "lucide-react";
import Visualizer from "@/components/Visualizer";
import { Slider } from "@/components/ui/slider";

const Session = () => {
  const [playing, setPlaying] = useState(true);
  const [volume, setVolume] = useState([70]);
  const [focusLevel, setFocusLevel] = useState(0);
  const navigate = useNavigate();

  // Simulate focus level changes
  useEffect(() => {
    const interval = setInterval(() => {
      setFocusLevel((prev) => {
        const change = (Math.random() - 0.5) * 20;
        return Math.max(0, Math.min(100, prev + change));
      });
    }, 2000);

    // Initialize with random focus
    setFocusLevel(Math.random() * 60 + 20);

    return () => clearInterval(interval);
  }, []);

  const getFocusColor = () => {
    if (focusLevel < 40) return "text-destructive";
    if (focusLevel < 70) return "text-accent";
    return "text-primary";
  };

  const getFocusLabel = () => {
    if (focusLevel < 40) return "Distracted";
    if (focusLevel < 70) return "Focused";
    return "Deep Focus";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-card to-muted flex flex-col relative overflow-hidden">
      {/* Animated background responding to focus */}
      <div className="absolute inset-0">
        <div 
          className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full blur-3xl transition-all duration-1000"
          style={{ 
            backgroundColor: `hsla(${focusLevel > 70 ? '185, 70%, 50%' : focusLevel > 40 ? '170, 60%, 55%' : '0, 70%, 60%'}, 0.15)`,
            transform: `scale(${0.8 + (focusLevel / 100) * 0.4})`
          }}
        />
        <div 
          className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full blur-3xl transition-all duration-1000"
          style={{ 
            backgroundColor: `hsla(${focusLevel > 70 ? '170, 60%, 55%' : focusLevel > 40 ? '195, 60%, 65%' : '20, 70%, 60%'}, 0.15)`,
            animationDelay: "1s",
            transform: `scale(${0.7 + (focusLevel / 100) * 0.5})`
          }}
        />
      </div>

      {/* Header */}
      <header className="relative z-10 p-6 flex justify-between items-center">
        <Button 
          variant="ghost" 
          onClick={() => navigate("/")}
          className="hover:bg-card/50"
        >
          End Session
        </Button>
        
        <div className="flex items-center gap-3">
          <Volume2 className="w-5 h-5 text-muted-foreground" />
          <Slider
            value={volume}
            onValueChange={setVolume}
            max={100}
            step={1}
            className="w-32"
          />
        </div>
      </header>

      {/* Main content */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 py-12">
        {/* Focus indicator */}
        <div className="mb-12 text-center">
          <div className="mb-4">
            <div className={`text-7xl font-bold transition-colors duration-500 ${getFocusColor()}`}>
              {Math.round(focusLevel)}%
            </div>
          </div>
          <div className={`text-xl font-medium transition-colors duration-500 ${getFocusColor()}`}>
            {getFocusLabel()}
          </div>
        </div>

        {/* Visualizer */}
        <div className="w-full max-w-4xl mb-12">
          <Visualizer />
        </div>

        {/* Controls */}
        <div className="flex items-center gap-6">
          <Button
            variant="outline"
            size="icon"
            className="w-12 h-12 rounded-full border-2"
          >
            <SkipForward className="w-5 h-5" />
          </Button>

          <Button
            size="icon"
            onClick={() => setPlaying(!playing)}
            className="w-16 h-16 rounded-full shadow-lg hover:shadow-glow transition-all duration-300"
          >
            {playing ? (
              <Pause className="w-6 h-6" />
            ) : (
              <Play className="w-6 h-6 ml-1" />
            )}
          </Button>

          <Button
            variant="outline"
            size="icon"
            className="w-12 h-12 rounded-full border-2"
          >
            <SkipForward className="w-5 h-5" />
          </Button>
        </div>

        {/* Status text */}
        <p className="mt-8 text-muted-foreground text-sm">
          {playing ? "Music adapting to your focus level..." : "Paused"}
        </p>
      </main>
    </div>
  );
};

export default Session;
