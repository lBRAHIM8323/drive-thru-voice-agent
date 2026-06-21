import { useCallback, useEffect, useRef, useState } from 'react';
import type { InferenceSession } from 'onnxruntime-web';

import type { WakeWordConfig } from '../api/types';

const SAMPLE_RATE = 16000;
const FFT_SIZE = 512;
const HOP_LENGTH = 160; // 10ms at 16kHz
const MEL_BANDS = 16;
const TIME_FRAMES = 96; // context window
const N_FFT_BINS = FFT_SIZE / 2 + 1;

function hzToMel(hz: number): number {
  return 2595 * Math.log10(1 + hz / 700);
}

function melToHz(mel: number): number {
  return 700 * (10 ** (mel / 2595) - 1);
}

function createMelFilterbank(
  sampleRate: number,
  nFft: number,
  nMels: number,
  fMin: number,
  fMax: number,
): Float64Array[] {
  const fftBins = nFft / 2 + 1;
  const melMin = hzToMel(fMin);
  const melMax = hzToMel(fMax);
  const melPoints = [];
  for (let i = 0; i < nMels + 2; i++) {
    const mel = melMin + (i / (nMels + 1)) * (melMax - melMin);
    melPoints.push(Math.floor((fftBins - 1) * melToHz(mel) / (sampleRate / 2)));
  }
  const filters: Float64Array[] = [];
  for (let m = 0; m < nMels; m++) {
    const filter = new Float64Array(fftBins);
    const start = melPoints[m];
    const center = melPoints[m + 1];
    const end = melPoints[m + 2];
    for (let k = start; k < center; k++) {
      filter[k] = (k - start) / (center - start);
    }
    for (let k = center; k < end; k++) {
      filter[k] = (end - k) / (end - center);
    }
    filters.push(filter);
  }
  return filters;
}

const MEL_FILTERS = createMelFilterbank(SAMPLE_RATE, FFT_SIZE, MEL_BANDS, 80, 7600);

function hannWindow(len: number): Float64Array {
  const w = new Float64Array(len);
  for (let i = 0; i < len; i++) {
    w[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (len - 1)));
  }
  return w;
}

const HANN = hannWindow(FFT_SIZE);

function computeMelSpectrogram(frame: Float32Array): Float64Array {
  const windowed = new Float64Array(FFT_SIZE);
  for (let i = 0; i < FFT_SIZE; i++) {
    windowed[i] = (i < frame.length ? frame[i] : 0) * HANN[i];
  }
  const real = new Float64Array(N_FFT_BINS);
  const imag = new Float64Array(N_FFT_BINS);
  for (let k = 0; k < N_FFT_BINS; k++) {
    for (let n = 0; n < FFT_SIZE; n++) {
      const angle = (-2 * Math.PI * k * n) / FFT_SIZE;
      real[k] += windowed[n] * Math.cos(angle);
      imag[k] += windowed[n] * Math.sin(angle);
    }
  }
  const power = new Float64Array(N_FFT_BINS);
  for (let k = 0; k < N_FFT_BINS; k++) {
    power[k] = real[k] * real[k] + imag[k] * imag[k];
  }
  const mel = new Float64Array(MEL_BANDS);
  for (let m = 0; m < MEL_BANDS; m++) {
    let sum = 0;
    for (let k = 0; k < N_FFT_BINS; k++) {
      sum += power[k] * MEL_FILTERS[m][k];
    }
    mel[m] = Math.max(0, Math.log(sum + 1e-10));
  }
  return mel;
}

export interface WakeWordDetection {
  phrase: string;
  confidence: number;
}

export interface UseWakeWordOptions {
  config: WakeWordConfig;
  onDetected: (detection: WakeWordDetection) => void;
}

export interface UseWakeWordResult {
  listening: boolean;
  error: string | null;
  supported: boolean;
}

export function useWakeWord({
  config,
  onDetected,
}: UseWakeWordOptions): UseWakeWordResult {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supported = typeof AudioContext !== 'undefined' && typeof navigator.mediaDevices?.getUserMedia === 'function';

  const sessionRef = useRef<InferenceSession | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const bufferRef = useRef<Float64Array[]>([]);
  const frameCountRef = useRef(0);
  const runningRef = useRef(false);

  const loadModel = useCallback(async () => {
    try {
      const { InferenceSession } = await import('onnxruntime-web');
      const session = await InferenceSession.create(config.model_url, {
        executionProviders: ['wasm', 'cpu'],
      });
      sessionRef.current = session;
    } catch {
      // model loading failed — detection won't work but UI should degrade
    }
  }, [config.model_url]);

  useEffect(() => {
    if (!config.enabled || !config.phrases.length) return;
    let cancelled = false;

    (async () => {
      try {
        await loadModel();
        if (cancelled) return;

        const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          ctx.close();
          return;
        }

        audioCtxRef.current = ctx;
        streamRef.current = stream;
        sourceRef.current = ctx.createMediaStreamSource(stream);

        const processor = ctx.createScriptProcessor(FFT_SIZE, 1, 1);
        processorRef.current = processor;

        const sesh = sessionRef.current;
        if (!sesh) {
          setError('Wake word model failed to load');
          return;
        }

        runningRef.current = true;

        processor.onaudioprocess = (e) => {
          if (!runningRef.current) return;
          const input = e.inputBuffer.getChannelData(0);

          // Downsample 48kHz → 16kHz if needed
          let samples: Float32Array;
          if (ctx.sampleRate === SAMPLE_RATE) {
            samples = input;
          } else {
            const ratio = ctx.sampleRate / SAMPLE_RATE;
            const len = Math.floor(input.length / ratio);
            samples = new Float32Array(len);
            for (let i = 0; i < len; i++) {
              const idx = Math.floor(i * ratio);
              samples[i] = input[Math.min(idx, input.length - 1)];
            }
          }

          // Compute mel frames from the audio chunk
          for (let offset = 0; offset + FFT_SIZE <= samples.length; offset += HOP_LENGTH) {
            const frame = samples.subarray(offset, offset + FFT_SIZE);
            const mel = computeMelSpectrogram(frame);
            bufferRef.current.push(mel);

            // Keep only the last TIME_FRAMES frames
            if (bufferRef.current.length > TIME_FRAMES) {
              bufferRef.current = bufferRef.current.slice(-TIME_FRAMES);
            }

            frameCountRef.current++;

            // Run inference once we have a full context window
            if (bufferRef.current.length === TIME_FRAMES && frameCountRef.current % 5 === 0) {
              runInference(sesh).catch(() => {});
            }
          }
        };

        sourceRef.current.connect(processor);
        processor.connect(ctx.destination);
        setListening(true);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Wake word init failed');
        }
      }
    })();

    return () => {
      cancelled = true;
      runningRef.current = false;
      setListening(false);
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      if (sourceRef.current) {
        sourceRef.current.disconnect();
        sourceRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close();
        audioCtxRef.current = null;
      }
    };
  }, [config.enabled, config.phrases, config.threshold, config.model_url, loadModel, onDetected]);

  async function runInference(sesh: InferenceSession) {
    if (!bufferRef.current.length) return;
    const buf = bufferRef.current;

    // Build input tensor: (1, 16, 96)
    const data = new Float32Array(MEL_BANDS * TIME_FRAMES);
    for (let t = 0; t < TIME_FRAMES; t++) {
      const frame = buf[t] ?? buf[buf.length - 1];
      for (let m = 0; m < MEL_BANDS; m++) {
        data[m * TIME_FRAMES + t] = Number(frame[m]);
      }
    }

    const { Tensor } = await import('onnxruntime-web');
    const inputTensor = new Tensor('float32', data, [1, MEL_BANDS, TIME_FRAMES]);
    const feeds: Record<string, typeof inputTensor> = {};
    feeds[sesh.inputNames[0]] = inputTensor;
    const results = await sesh.run(feeds);
    const output = results[sesh.outputNames[0]];
    const score = output.data as Float32Array;

    if (score[0] > config.threshold && config.phrases.length > 0) {
      runningRef.current = false;
      onDetected({ phrase: config.phrases[0], confidence: score[0] });
    }
  }

  return { listening, error, supported };
}
