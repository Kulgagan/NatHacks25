import { useEffect, useRef } from "react";

const Visualizer = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Wave parameters
    let time = 0;
    const waves = [
      { amplitude: 30, frequency: 0.02, speed: 0.03, color: "185, 70%, 50%" },
      { amplitude: 25, frequency: 0.025, speed: 0.025, color: "170, 60%, 55%" },
      { amplitude: 20, frequency: 0.03, speed: 0.02, color: "195, 60%, 65%" },
    ];

    // Animation loop
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      const centerY = canvas.height / 2;

      waves.forEach((wave, index) => {
        ctx.beginPath();
        ctx.moveTo(0, centerY);

        // Draw wave
        for (let x = 0; x < canvas.width; x++) {
          const y = centerY + 
            Math.sin(x * wave.frequency + time * wave.speed) * wave.amplitude +
            Math.sin(x * wave.frequency * 2 + time * wave.speed * 1.5) * (wave.amplitude / 2);
          
          ctx.lineTo(x, y);
        }

        // Gradient stroke
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
        gradient.addColorStop(0, `hsla(${wave.color}, 0.1)`);
        gradient.addColorStop(0.5, `hsla(${wave.color}, 0.6)`);
        gradient.addColorStop(1, `hsla(${wave.color}, 0.1)`);

        ctx.strokeStyle = gradient;
        ctx.lineWidth = 3;
        ctx.lineCap = "round";
        ctx.stroke();
      });

      time += 1;
      requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener("resize", resizeCanvas);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-64 md:h-96"
      style={{ filter: "blur(0.5px)" }}
    />
  );
};

export default Visualizer;
