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
  MenuItem,
  MenuItemCreate,
  MenuItemUpdate,
  ParserConfig,
  ParserConfigUpdate,
  UUID,
} from './types';

export const qk = {
  branches: ['branches'] as const,
  menu: (category?: string) => ['menu', category ?? 'all'] as const,
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

export function useMenu(category?: string) {
  return useQuery({
    queryKey: qk.menu(category),
    queryFn: () =>
      api.get<MenuItem[]>(`/menu${category ? `?category=${encodeURIComponent(category)}` : ''}`),
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

// --- connection (customer page) -------------------------------------------

export function useCreateConnection() {
  return useMutation({
    mutationFn: (configId?: string) =>
      api.post<ConnectionInfo>('/connection', configId ? { config_id: configId } : {}),
  });
}
