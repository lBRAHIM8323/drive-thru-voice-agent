import type { AgentConfig } from '../api/types';

// Mirrors the server's AgentConfig defaults (schemas/agent_config.py) so the
// "create" form starts from the same baseline the agent would otherwise use.
export function defaultAgentConfig(): AgentConfig {
  return {
    instructions:
      'You are a friendly drive-thru attendant. Keep replies short and natural.',
    greeting: null,
    stt: {
      provider: 'deepgram',
      model: 'nova-3',
      language: 'en',
      keyterms: [],
      extra: {},
    },
    llm: {
      provider: 'openai',
      model: 'gpt-4.1-mini',
      temperature: null,
      parallel_tool_calls: null,
      extra: {},
    },
    tts: {
      provider: 'cartesia',
      model: 'sonic-3',
      voice: null,
      language: null,
      extra: {},
    },
    vad: {
      enabled: true,
      min_speech_duration: null,
      min_silence_duration: null,
      activation_threshold: null,
    },
    turn_detection: { mode: 'multilingual' },
    session: {
      max_tool_steps: 10,
      allow_interruptions: null,
      min_interruption_duration: null,
      min_endpointing_delay: null,
      max_endpointing_delay: null,
      preemptive_generation: null,
    },
    background_audio: { enabled: true, volume: 1.0 },
    ui: { visualizer: 'bar', accent_color: null, title: null },
  };
}
