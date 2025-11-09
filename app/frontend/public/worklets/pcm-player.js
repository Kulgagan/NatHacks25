class PCMPlayer extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];              // Array<Float32Array>
    this.buffer = null;
    this.readIdx = 0;

    this.gain = 1.0;             // simple software gain for fade-outs
    this.fadeSamples = 0;        // remaining fade samples
    this.MAX_QUEUE_SAMPLES = sampleRate * 2; // cap ~2s max

    this.queuedSamples = 0;

    this.port.onmessage = (e) => {
      const msg = e.data || {};
      if (msg.type === 'chunk') {
        let arr;
        if (msg.payload instanceof ArrayBuffer) {
          arr = new Float32Array(msg.payload);
        } else if (msg.payload instanceof Float32Array) {
          arr = msg.payload;
        } else return;

        // cap total queued samples (drop oldest first)
        while (this.queuedSamples + arr.length > this.MAX_QUEUE_SAMPLES && this.queue.length) {
          const old = this.queue.shift();
          this.queuedSamples -= old.length;
        }
        this.queue.push(new Float32Array(arr));
        this.queuedSamples += arr.length;

      } else if (msg.type === 'flush') {
        // start a short fade and clear all pending audio
        this.queue = [];
        this.buffer = null;
        this.readIdx = 0;
        this.queuedSamples = 0;
        this.fadeSamples = Math.floor(sampleRate * 0.2); // 200 ms fade
      }
    };
  }

  _pullNextChunk() {
    this.buffer = this.queue.length ? this.queue.shift() : null;
    if (this.buffer) this.queuedSamples -= this.buffer.length;
    this.readIdx = 0;
  }

  process(inputs, outputs/*, parameters*/) {
    const out = outputs[0][0]; // mono
    let i = 0;

    while (i < out.length) {
      if (!this.buffer || this.readIdx >= this.buffer.length) {
        this._pullNextChunk();
        if (!this.buffer) {
          // no data; write zeros (never loop stale buffers)
          while (i < out.length) {
            let s = 0.0;
            if (this.fadeSamples > 0) {
              // apply linear fade to silence
              const k = this.fadeSamples / (sampleRate * 0.2);
              this.gain = Math.max(0, k); // 1 -> 0 over 200ms
              this.fadeSamples--;
            } else {
              this.gain = 0.0; // fully silent after fade
            }
            out[i++] = s * this.gain;
          }
          return true;
        }
      }

      const copyCount = Math.min(out.length - i, this.buffer.length - this.readIdx);
      const src = this.buffer.subarray(this.readIdx, this.readIdx + copyCount);
      for (let k = 0; k < copyCount; k++) {
        let s = src[k];
        if (this.fadeSamples > 0) {
          const kk = this.fadeSamples / (sampleRate * 0.2);
          this.gain = Math.max(0, kk);
          this.fadeSamples--;
        } else {
          this.gain = 1.0;
        }
        out[i + k] = s * this.gain;
      }
      i += copyCount;
      this.readIdx += copyCount;
    }
    return true;
  }
}

registerProcessor('pcm-player', PCMPlayer);
