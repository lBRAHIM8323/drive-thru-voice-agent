// Select options for providers and a few suggested models. Models are free-text
// (any string is allowed), these are just convenience presets in the UI.

import type {
  Dietary,
  LLMProvider,
  ParserProvider,
  STTProvider,
  TTSProvider,
  TurnDetectionMode,
  Visualizer,
} from '../api/types';

export const sttProviders: STTProvider[] = ['deepgram', 'assemblyai'];
export const llmProviders: LLMProvider[] = ['openai', 'anthropic', 'google'];
export const ttsProviders: TTSProvider[] = ['cartesia', 'elevenlabs'];
export const parserProviders: ParserProvider[] = ['openai', 'anthropic', 'google'];
export const turnModes: TurnDetectionMode[] = ['multilingual', 'english', 'vad', 'stt', 'none'];
export const visualizers: Visualizer[] = ['bar', 'grid', 'radial', 'wave', 'aura'];
export const itemSizes = ['S', 'M', 'L', 'XL'] as const;

export const dietaryOptions: { value: Dietary; label: string }[] = [
  { value: 'veg', label: 'Vegetarian' },
  { value: 'non_veg', label: 'Non-vegetarian' },
  { value: 'vegan', label: 'Vegan' },
];

// Suggested dietary/allergen tags (the field is free-form, these are presets).
export const suggestedTags = [
  'lactose_free',
  'gluten_free',
  'nut_free',
  'halal',
  'spicy',
  'low_calorie',
] as const;

export const suggestedLLMModels: Record<LLMProvider, string[]> = {
  openai: ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o', 'gpt-4o-mini'],
  anthropic: ['claude-haiku-4-5', 'claude-sonnet-4-6', 'claude-opus-4-8'],
  google: ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-2.5-pro'],
};

export const suggestedSTTModels: Record<STTProvider, string[]> = {
  deepgram: ['nova-3', 'nova-2'],
  assemblyai: ['universal', 'best'],
};

export const suggestedTTSModels: Record<TTSProvider, string[]> = {
  cartesia: ['sonic-3', 'sonic-2'],
  elevenlabs: ['eleven_turbo_v2_5', 'eleven_multilingual_v2'],
};

export function selectData(values: readonly string[]) {
  return values.map((v) => ({ value: v, label: v }));
}
