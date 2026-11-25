(() => {
  const FRAME_MS = 20;
  const DST_RATE = 16000;
  const FRAME_SAMPLES = (DST_RATE * FRAME_MS) / 1000;
  const WS_PATH = "/v1/audio";

  const logEl = document.getElementById("log");
  const framesEl = document.getElementById("frames");
  const aecEl = document.getElementById("aec");
  const nsEl = document.getElementById("ns");
  const startBtn = document.getElementById("start");
  const stopBtn = document.getElementById("stop");

  let socket = null;
  let audioCtx = null;
  let workletNode = null;
  let mediaStream = null;
  let frameIndex = 0;
  let pending = new Float32Array(0);

  function log(line) {
    logEl.textContent += line + "\n";
  }

  function encodeHello(sessionId, aec, ns) {
    const json = JSON.stringify({
      session_id: sessionId,
      sample_rate_hz: DST_RATE,
      frame_samples: FRAME_SAMPLES,
      aec,
      ns,
    });
    const payload = new TextEncoder().encode(json);
    const out = new Uint8Array(5 + payload.length);
    out[0] = 0x01;
    new DataView(out.buffer).setUint32(1, payload.length, true);
    out.set(payload, 5);
    return out;
  }

  function encodePcm(index, int16) {
    const out = new Uint8Array(5 + int16.byteLength);
    out[0] = 0x02;
    new DataView(out.buffer).setUint32(1, index, true);
    out.set(new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength), 5);
    return out;
  }

  function encodeAck(index) {
    const out = new Uint8Array(5);
    out[0] = 0x03;
    new DataView(out.buffer).setUint32(1, index, true);
    return out;
  }

  function encodeClose() {
    return new Uint8Array([0x04]);
  }

  function downsampleTo16k(input, srcRate) {
    if (srcRate === DST_RATE) return input;
    const ratio = srcRate / DST_RATE;
    const n = Math.floor(input.length / ratio);
    const out = new Float32Array(n);
    for (let i = 0; i < n; i += 1) {
      out[i] = input[Math.floor(i * ratio)];
    }
    return out;
  }

  function floatToPcm16(floatBuf) {
    const out = new Int16Array(floatBuf.length);
    for (let i = 0; i < floatBuf.length; i += 1) {
      const s = Math.max(-1, Math.min(1, floatBuf[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
  }

  function concat(a, b) {
    const out = new Float32Array(a.length + b.length);
    out.set(a, 0);
    out.set(b, a.length);
    return out;
  }

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: { exact: true },
        noiseSuppression: { exact: true },
        channelCount: { ideal: 1 },
      },
    });
    mediaStream = stream;
    const track = stream.getAudioTracks()[0];
    const settings = track.getSettings();
    const aec = Boolean(settings.echoCancellation);
    const ns = Boolean(settings.noiseSuppression);
    aecEl.textContent = String(aec);
    nsEl.textContent = String(ns);
    log("track settings " + JSON.stringify(settings));

    audioCtx = new AudioContext();
    const srcRate = audioCtx.sampleRate;
    const sessionId = crypto.randomUUID();
    const proto = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${proto}://${location.host}${WS_PATH}`);
    socket.binaryType = "arraybuffer";
    await new Promise((resolve, reject) => {
      socket.onopen = resolve;
      socket.onerror = () => reject(new Error("ws error"));
    });
    socket.send(encodeHello(sessionId, aec, ns));
    log("hello sent " + sessionId);

    socket.onmessage = (ev) => {
      const data = new Uint8Array(ev.data);
      if (data.length >= 5 && data[0] === 0x02) {
        const idx = new DataView(data.buffer, data.byteOffset + 1, 4).getUint32(0, true);
        socket.send(encodeAck(idx));
      }
    };

    const workletSrc = `
      class CaptureProcessor extends AudioWorkletProcessor {
        process(inputs) {
          const ch = inputs[0] && inputs[0][0];
          if (ch) this.port.postMessage(new Float32Array(ch));
          return true;
        }
      }
      registerProcessor("capture", CaptureProcessor);
    `;
    const blob = new Blob([workletSrc], { type: "text/javascript" });
    const url = URL.createObjectURL(blob);
    await audioCtx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const src = audioCtx.createMediaStreamSource(stream);
    workletNode = new AudioWorkletNode(audioCtx, "capture");
    workletNode.port.onmessage = (ev) => {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      const down = downsampleTo16k(ev.data, srcRate);
      pending = concat(pending, down);
      while (pending.length >= FRAME_SAMPLES) {
        const slice = pending.subarray(0, FRAME_SAMPLES);
        pending = pending.subarray(FRAME_SAMPLES);
        const pcm = floatToPcm16(slice);
        socket.send(encodePcm(frameIndex, pcm));
        frameIndex += 1;
        framesEl.textContent = String(frameIndex);
      }
    };
    const mute = audioCtx.createGain();
    mute.gain.value = 0;
    src.connect(workletNode);
    workletNode.connect(mute);
    mute.connect(audioCtx.destination);
    startBtn.disabled = true;
    stopBtn.disabled = false;
  }

  async function stop() {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(encodeClose());
      socket.close();
    }
    socket = null;
    if (workletNode) workletNode.disconnect();
    workletNode = null;
    if (audioCtx) await audioCtx.close();
    audioCtx = null;
    if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
    pending = new Float32Array(0);
    startBtn.disabled = false;
    stopBtn.disabled = true;
    log("stopped at frame " + frameIndex);
  }

  startBtn.addEventListener("click", () => {
    start().catch((err) => log(String(err)));
  });
  stopBtn.addEventListener("click", () => {
    stop().catch((err) => log(String(err)));
  });
})();
