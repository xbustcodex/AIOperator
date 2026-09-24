/* Buster GUI — Voice/live interface.

Platform audio stays behind an AudioBackend interface so the Buster product
UI is portable across Buster deployment targets. A browser implementation is
provided where the platform exposes getUserMedia; otherwise the backends()
list simply reports it as unavailable and the UI degrades gracefully to text.
*/

export class AudioBackend {
  constructor(name) {
    this.name = name;
  }
  async probe() { return { available: false, name: this.name }; }
  async listen(onTranscript) { void onTranscript; throw new Error("not implemented"); }
  stop() {}
}

export class BrowserAudioBackend extends AudioBackend {
  constructor() {
    super("browser");
    this._stream = null;
    this._recorder = null;
  }

  async probe() {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      return { available: false, name: this.name,
               reason: "Speech input is not available on this platform" };
    }
    try {
      const supported = window.SpeechRecognition || window.webkitSpeechRecognition;
      return { available: Boolean(supported), name: this.name,
               listening: this._stream != null };
    } catch {
      return { available: false, name: this.name };
    }
  }

  async listen(onTranscript) {
    const supported = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!supported) throw new Error("speech recognition unavailable");
    const rec = new supported();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.onresult = (event) => {
      const text = event.results[0][0].transcript;
      if (text) onTranscript({ text, final: true });
    };
    rec.onend = () => rec.stop();
    rec.start();
    this._rec = rec;
    return { started: true };
  }

  stop() {
    if (this._rec) try { this._rec.stop(); } catch (_) {}
  }
}

export const backends = () =>
  [new BrowserAudioBackend(), ...(globalThis.__busterAudioBackends || [])];

export async function bestBackend() {
  for (const backend of backends()) {
    const probe = await backend.probe();
    if (probe.available) return backend;
  }
  return null;
}