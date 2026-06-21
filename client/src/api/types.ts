// Types mirroring the FastAPI server schemas (backend/server/src/server/schemas).
// Keep in sync with the server; the JSON shape is the contract.

export type UUID = string;

// --- providers / enums ----------------------------------------------------

export type STTProvider = 'deepgram' | 'assemblyai';
export type LLMProvider = 'openai' | 'anthropic' | 'google';
export type TTSProvider = 'cartesia' | 'elevenlabs';
export type TurnDetectionMode = 'multilingual' | 'english' | 'vad' | 'stt' | 'none';
export type ParserProvider = 'openai' | 'anthropic' | 'google';
export type ItemSize = 'S' | 'M' | 'L' | 'XL';
export type Dietary = 'veg' | 'non_veg' | 'vegan';
export type DocumentStatus = 'uploaded' | 'parsing' | 'parsed' | 'failed' | 'confirmed';

// --- agent config ---------------------------------------------------------

export interface STTConfig {
  provider: STTProvider;
  model: string;
  language: string;
  keyterms: string[];
  extra: Record<string, unknown>;
}

export interface LLMConfig {
  provider: LLMProvider;
  model: string;
  temperature: number | null;
  parallel_tool_calls: boolean | null;
  extra: Record<string, unknown>;
}

export interface TTSConfig {
  provider: TTSProvider;
  model: string;
  voice: string | null;
  language: string | null;
  extra: Record<string, unknown>;
}

export interface VADConfig {
  enabled: boolean;
  min_speech_duration: number | null;
  min_silence_duration: number | null;
  activation_threshold: number | null;
}

export interface TurnDetectionConfig {
  mode: TurnDetectionMode;
}

export interface SessionConfig {
  max_tool_steps: number;
  allow_interruptions: boolean | null;
  min_interruption_duration: number | null;
  min_endpointing_delay: number | null;
  max_endpointing_delay: number | null;
  preemptive_generation: boolean | null;
}

export interface BackgroundAudioConfig {
  enabled: boolean;
  volume: number;
}

export type Visualizer = 'bar' | 'grid' | 'radial' | 'wave' | 'aura';

export interface UIConfig {
  visualizer: Visualizer;
  accent_color: string | null;
  title: string | null;
}

export interface WakeWordConfig {
  enabled: boolean;
  phrases: string[];
  threshold: number;
  model_url: string;
}

export interface AgentConfig {
  instructions: string;
  greeting: string | null;
  wakewords: WakeWordConfig;
  stt: STTConfig;
  llm: LLMConfig;
  tts: TTSConfig;
  vad: VADConfig;
  turn_detection: TurnDetectionConfig;
  session: SessionConfig;
  background_audio: BackgroundAudioConfig;
  ui: UIConfig;
}

export interface AgentConfigSummary {
  id: string;
  name: string;
  branch_id: UUID | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentConfigCreate {
  id?: string | null;
  name: string;
  branch_id?: UUID | null;
  is_active: boolean;
  config: AgentConfig;
}

export interface AgentConfigUpdate {
  name?: string | null;
  branch_id?: UUID | null;
  is_active?: boolean | null;
  config?: AgentConfig | null;
}

// --- menu -----------------------------------------------------------------

export interface SizeOption {
  size: ItemSize;
  price: number;
  calories: number | null;
}

export interface MenuItem {
  id: string;
  name: string;
  category: string;
  description: string | null;
  available: boolean;
  voice_alias: string | null;
  image_url: string | null;
  calories: number | null;
  price: number | null;
  currency: string;
  branch_id: UUID | null;
  dietary: Dietary | null;
  tags: string[];
  serves: number | null;
  is_favorite: boolean;
  offer_price: number | null;
  offer_until: string | null; // ISO timestamp
  sizes: SizeOption[];
}

export type MenuItemCreate = Omit<MenuItem, 'id'> & { id?: string | null };
export type MenuItemUpdate = Partial<Omit<MenuItem, 'id'>>;

// --- documents ------------------------------------------------------------

export interface DocumentRead {
  id: UUID;
  branch_id: UUID | null;
  filename: string | null;
  content_type: string | null;
  status: DocumentStatus;
  parser_provider: string | null;
  parser_model: string | null;
  items: MenuItemCreate[];
  error: string | null;
  created_at: string | null;
  parsed_at: string | null;
}

export type ConfirmMode = 'merge' | 'replace';

// --- branches -------------------------------------------------------------

export interface Branch {
  id: UUID;
  name: string;
  slug: string;
  address: string | null;
  city: string | null;
  country: string | null;
  currency: string;
  timezone: string;
  phone: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface BranchCreate {
  name: string;
  slug?: string | null;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  currency?: string;
  timezone?: string;
  phone?: string | null;
  is_active?: boolean;
}

export type BranchUpdate = Partial<Omit<BranchCreate, 'slug'>>;

// --- parser config --------------------------------------------------------

export interface ParserConfig {
  provider: ParserProvider;
  model: string;
  temperature: number | null;
  system_prompt: string | null;
}

export type ParserConfigUpdate = Partial<ParserConfig>;

// --- connection (customer page) -------------------------------------------

export interface ConnectionInfo {
  server_url: string;
  token: string;
  room_name: string;
  identity: string;
  config_id: string;
  ui: UIConfig;
  wakewords: WakeWordConfig | null;
}

// --- auth ------------------------------------------------------------------

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export type UserRole = 'admin' | 'manager' | 'staff';

export interface User {
  id: UUID;
  username: string;
  email: string | null;
  role: UserRole;
  branch_id: UUID | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserCreate {
  username: string;
  password: string;
  email?: string | null;
  role?: UserRole;
  branch_id?: UUID | null;
  is_active?: boolean;
}

export type UserUpdate = Partial<Omit<UserCreate, 'username'>>;

// --- menu (pushed from the agent over RPC `set_menu_content`) ---------------

export interface MenuPayload {
  currency: string;
  items: MenuItem[];
}

// --- cart (pushed from the agent over RPC `set_cart_content`) --------------

export interface CartItem {
  name: string;
  details: string | null;
  quantity: number;
  unit_price: number;
  line_total: number;
  image_url: string | null;
}

export interface CartPayload {
  currency: string;
  items: CartItem[];
  total: number;
}

// --- sessions & orders -----------------------------------------------------

export interface OrderItemRead {
  id: UUID;
  order_id: UUID;
  menu_item_id: string | null;
  name_snapshot: string;
  size: string | null;
  quantity: number;
  unit_price: number;
  total_price: number;
  notes: Record<string, unknown> | null;
}

export interface OrderRead {
  id: UUID;
  session_id: UUID | null;
  branch_id: UUID | null;
  status: string;
  subtotal: number;
  tax: number;
  total: number;
  currency: string;
  placed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  items: OrderItemRead[];
}

export interface SessionRead {
  id: UUID;
  branch_id: UUID | null;
  agent_config_id: string | null;
  room_name: string | null;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  audio_url: string | null;
  transcript: Record<string, unknown> | null;
  orders: OrderRead[];
}
