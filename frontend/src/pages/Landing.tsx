import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Brain, Waves } from "lucide-react";

const Landing = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-card to-muted overflow-hidden relative">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-20 left-10 w-72 h-72 bg-primary/10 rounded-full blur-3xl animate-pulse-soft" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse-soft" style={{ animationDelay: "2s" }} />
      </div>

      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-6 text-center">
        {/* Logo/Icon */}
        <div className="mb-8 animate-float">
          <div className="relative">
            <Brain className="w-20 h-20 text-primary" strokeWidth={1.5} />
            <Waves className="w-12 h-12 text-accent absolute -bottom-2 -right-2 animate-pulse-soft" strokeWidth={1.5} />
          </div>
        </div>

        {/* Hero content */}
        <div className="max-w-3xl animate-fade-in-up">
          <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
            Be More Productive Now
          </h1>
          
          <p className="text-xl md:text-2xl text-muted-foreground mb-12 max-w-2xl mx-auto leading-relaxed">
            Harness the power of your brain waves with Muse 2. 
            Let adaptive music guide you into deep focus and sustained productivity.
          </p>

          <Button
            size="lg"
            onClick={() => navigate("/connect")}
            className="px-10 py-6 text-lg rounded-full shadow-lg hover:shadow-glow transition-all duration-300 hover:scale-105"
          >
            Get Started
          </Button>
        </div>

        {/* Features preview */}
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl w-full">
          <div className="p-6 rounded-2xl bg-card/50 backdrop-blur-sm border border-border/50 hover:border-primary/50 transition-all duration-300">
            <Brain className="w-10 h-10 text-primary mb-4 mx-auto" strokeWidth={1.5} />
            <h3 className="font-semibold text-lg mb-2">EEG Detection</h3>
            <p className="text-sm text-muted-foreground">Real-time brain activity monitoring</p>
          </div>
          
          <div className="p-6 rounded-2xl bg-card/50 backdrop-blur-sm border border-border/50 hover:border-primary/50 transition-all duration-300">
            <Waves className="w-10 h-10 text-accent mb-4 mx-auto" strokeWidth={1.5} />
            <h3 className="font-semibold text-lg mb-2">Adaptive Music</h3>
            <p className="text-sm text-muted-foreground">Music that responds to your focus</p>
          </div>
          
          <div className="p-6 rounded-2xl bg-card/50 backdrop-blur-sm border border-border/50 hover:border-primary/50 transition-all duration-300">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-accent mb-4 mx-auto animate-scale-pulse" />
            <h3 className="font-semibold text-lg mb-2">Flow State</h3>
            <p className="text-sm text-muted-foreground">Achieve peak performance effortlessly</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Landing;
