import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Bluetooth, Loader2 } from "lucide-react";
import { toast } from "sonner";

const Connect = () => {
  const [connecting, setConnecting] = useState(false);
  const navigate = useNavigate();

  const handleConnect = async () => {
    setConnecting(true);
    
    // Simulate connection process
    toast.info("Searching for Muse 2 device...");
    
    setTimeout(() => {
      toast.success("Connected to Muse 2!");
      setTimeout(() => {
        navigate("/session");
      }, 1000);
    }, 2500);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-card to-muted flex items-center justify-center px-6 relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0">
        <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-primary/20 rounded-full blur-3xl animate-pulse-soft" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-accent/20 rounded-full blur-3xl animate-pulse-soft" style={{ animationDelay: "1.5s" }} />
      </div>

      <div className="relative z-10 text-center max-w-lg w-full">
        {/* Connection status indicator */}
        <div className="mb-8 flex justify-center">
          <div className={`relative ${connecting ? 'animate-scale-pulse' : ''}`}>
            <Bluetooth className="w-24 h-24 text-primary" strokeWidth={1.5} />
            {connecting && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-32 h-32 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
              </div>
            )}
          </div>
        </div>

        <h1 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          Connect Your Muse 2
        </h1>

        <p className="text-lg text-muted-foreground mb-10 leading-relaxed">
          {connecting 
            ? "Establishing connection with your device..." 
            : "Make sure your Muse 2 headband is powered on and nearby."
          }
        </p>

        <Button
          size="lg"
          onClick={handleConnect}
          disabled={connecting}
          className="px-10 py-6 text-lg rounded-full shadow-lg hover:shadow-glow transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {connecting ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Connecting...
            </>
          ) : (
            "Connect Device"
          )}
        </Button>

        <div className="mt-12 p-6 rounded-2xl bg-card/50 backdrop-blur-sm border border-border/50">
          <h3 className="font-semibold mb-3">Connection Tips</h3>
          <ul className="text-sm text-muted-foreground space-y-2 text-left">
            <li className="flex items-start">
              <span className="text-primary mr-2">•</span>
              <span>Ensure Bluetooth is enabled on your device</span>
            </li>
            <li className="flex items-start">
              <span className="text-primary mr-2">•</span>
              <span>Place the Muse 2 headband on your forehead</span>
            </li>
            <li className="flex items-start">
              <span className="text-primary mr-2">•</span>
              <span>Keep the headband within 10 feet of your device</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Connect;
