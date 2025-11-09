
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.readIndex = 0;
    this.current = null;
    this.port.onmessage = (e) => {
      if (e.data && e.data.type === 'chunk') {
        // Expect Float32Array mono
        this.queue.push(e.data.payload);
      }
    };
  }

  process(_inputs, outputs, _params) {
    const output = outputs[0];
    const left = output[0];
    const right = output.length > 1 ? output[1] : output[0];
    for (let i = 0; i < left.length; i++) {
      if (!this.current || this.readIndex >= this.current.length) {
        this.current = this.queue.shift() || null;
        this.readIndex = 0;
      }
      const s = this.current ? this.current[this.readIndex++] : 0.0;
      left[i] = s;
      right[i] = s;
    }
    return true;
  }
}

registerProcessor('pcm-player', PCMPlayerProcessor);
