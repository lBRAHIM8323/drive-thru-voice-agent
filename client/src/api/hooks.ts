import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type {
  AgentConfig,
  AgentConfigCreate,
  AgentConfigSummary,
  AgentConfigUpdate,
  Branch,
  BranchCreate,
  BranchUpdate,
  ConfirmMode,
  ConnectionInfo,
  DocumentRead,
  LoginRequest,
  MenuItem,
  MenuItemCreate,
  MenuItemUpdate,
  ParserConfig,
  ParserConfigUpdate,
  SessionRead,
  TokenResponse,
  UUID,
  User,
  UserCreate,
  UserUpdate,
} from './types';

// --- auth ------------------------------------------------------------------

export function useLogin() {
  return useMutation({
    mutationFn: (body: LoginRequest) => api.post<TokenResponse>('/auth/login', body),
  });
}

export function useMe() {
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => api.get<User>('/auth/me'),
    retry: false,
    staleTime: 60_000,
  });
}

// --- users (admin only) ----------------------------------------------------

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => api.get<User[]>('/users'),
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UserCreate) => api.post<User>('/users', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: UUID; body: UserUpdate }) =>
      api.patch<User>(`/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

// --- query keys ------------------------------------------------------------

export interface MenuFilters {
  category?: string;
  favorite?: boolean;
  on_offer?: boolean;
}

export const qk = {
  branches: ['branches'] as const,
  menu: (filters?: MenuFilters) => ['menu', filters ?? {}] as const,
  documents: ['documents'] as const,
  document: (id: UUID) => ['documents', id] as const,
  agentConfigs: ['agent-configs'] as const,
  agentConfig: (id: string) => ['agent-configs', id] as const,
  parserConfig: ['parser-config'] as const,
};

// --- branches -------------------------------------------------------------

export function useBranches() {
  return useQuery({ queryKey: qk.branches, queryFn: () => api.get<Branch[]>('/branches') });
}

export function useCreateBranch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BranchCreate) => api.post<Branch>('/branches', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.branches }),
  });
}

export function useUpdateBranch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: UUID; body: BranchUpdate }) =>
      api.patch<Branch>(`/branches/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.branches }),
  });
}

export function useDeleteBranch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/branches/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.branches }),
  });
}

// --- menu -----------------------------------------------------------------

function buildQuery(filters?: MenuFilters): string {
  if (!filters) return '';
  const parts: string[] = [];
  if (filters.category) parts.push(`category=${encodeURIComponent(filters.category)}`);
  if (filters.favorite != null) parts.push(`favorite=${filters.favorite}`);
  if (filters.on_offer != null) parts.push(`on_offer=${filters.on_offer}`);
  return parts.length ? `?${parts.join('&')}` : '';
}

export function useMenu(filters?: MenuFilters) {
  return useQuery({
    queryKey: qk.menu(filters),
    queryFn: () => api.get<MenuItem[]>(`/menu${buildQuery(filters)}`),
  });
}

export function useCreateMenuItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MenuItemCreate) => api.post<MenuItem>('/menu', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu'] }),
  });
}

export function useUpdateMenuItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: MenuItemUpdate }) =>
      api.patch<MenuItem>(`/menu/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu'] }),
  });
}

export function useDeleteMenuItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del<void>(`/menu/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu'] }),
  });
}

// --- documents ------------------------------------------------------------

export function useDocuments() {
  return useQuery({ queryKey: qk.documents, queryFn: () => api.get<DocumentRead[]>('/documents') });
}

export function useDocument(id: UUID | undefined) {
  return useQuery({
    queryKey: id ? qk.document(id) : ['documents', 'none'],
    queryFn: () => api.get<DocumentRead>(`/documents/${id}`),
    enabled: !!id,
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { file?: File; text?: string }) => {
      const form = new FormData();
      if (input.file) form.append('file', input.file);
      if (input.text) form.append('text', input.text);
      return api.postForm<DocumentRead>('/documents', form);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.documents }),
  });
}

export function useUpdateDocumentItems() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, items }: { id: UUID; items: MenuItemCreate[] }) =>
      api.patch<DocumentRead>(`/documents/${id}`, { items }),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: qk.documents });
      qc.invalidateQueries({ queryKey: qk.document(id) });
    },
  });
}

export function useConfirmDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, mode }: { id: UUID; mode: ConfirmMode }) =>
      api.post<string[]>(`/documents/${id}/confirm?mode=${mode}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.documents });
      qc.invalidateQueries({ queryKey: ['menu'] });
    },
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.documents }),
  });
}

// --- agent configs --------------------------------------------------------

export function useAgentConfigs() {
  return useQuery({
    queryKey: qk.agentConfigs,
    queryFn: () => api.get<AgentConfigSummary[]>('/agent-configs'),
  });
}

export function useAgentConfig(id: string | undefined) {
  return useQuery({
    queryKey: id ? qk.agentConfig(id) : ['agent-configs', 'none'],
    queryFn: () => api.get<AgentConfig>(`/agent-configs/${id}`),
    enabled: !!id,
  });
}

export function useCreateAgentConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AgentConfigCreate) =>
      api.post<AgentConfigSummary>('/agent-configs', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.agentConfigs }),
  });
}

export function useUpdateAgentConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AgentConfigUpdate }) =>
      api.patch<AgentConfigSummary>(`/agent-configs/${id}`, body),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: qk.agentConfigs });
      qc.invalidateQueries({ queryKey: qk.agentConfig(id) });
    },
  });
}

export function useDeleteAgentConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del<void>(`/agent-configs/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.agentConfigs }),
  });
}

// --- parser config --------------------------------------------------------

export function useParserConfig() {
  return useQuery({
    queryKey: qk.parserConfig,
    queryFn: () => api.get<ParserConfig>('/parser-config'),
  });
}

export function useUpdateParserConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ParserConfigUpdate) => api.put<ParserConfig>('/parser-config', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.parserConfig }),
  });
}

// --- sessions (listen-in) --------------------------------------------------

export const useSessions = () =>
  useQuery({
    queryKey: ['sessions'],
    queryFn: () => api.get<SessionRead[]>('/sessions'),
  });

export const useSession = (id: UUID | undefined) =>
  useQuery({
    queryKey: ['sessions', id],
    queryFn: () => api.get<SessionRead>(`/sessions/${id}`),
    enabled: !!id,
  });

// --- connection (customer page) -------------------------------------------

export function useCreateConnection() {
  return useMutation({
    mutationFn: (configId?: string) =>
      api.post<ConnectionInfo>('/connection', configId ? { config_id: configId } : {}),
  });
}
