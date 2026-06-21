import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Switch,
  Table,
  Text,
} from '@mantine/core';
import { IconEdit, IconPlus, IconTrash } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';

import {
  useAgentConfigs,
  useDeleteAgentConfig,
  useUpdateAgentConfig,
} from '../../api/hooks';
import type { AgentConfigSummary } from '../../api/types';
import { AsyncState } from '../../components/AsyncState';
import { PageHeader } from '../../components/PageHeader';
import { confirmDelete } from '../../components/confirmDelete';
import { notifyError, notifySuccess } from '../../lib/notify';

export function AgentConfigsPage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useAgentConfigs();
  const updateMut = useUpdateAgentConfig();
  const deleteMut = useDeleteAgentConfig();

  async function toggleActive(c: AgentConfigSummary) {
    try {
      await updateMut.mutateAsync({ id: c.id, body: { is_active: !c.is_active } });
    } catch (e) {
      notifyError(e);
    }
  }

  async function remove(c: AgentConfigSummary) {
    if (!(await confirmDelete(`Delete agent config "${c.name || c.id}"?`))) return;
    try {
      await deleteMut.mutateAsync(c.id);
      notifySuccess('Config deleted');
    } catch (e) {
      notifyError(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Agent configs"
        description="Each config defines the agent's STT, LLM, TTS, prompt and behavior. The voice-agent fetches one by id."
        actions={
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => navigate('/platform/agent-configs/new')}
          >
            New config
          </Button>
        }
      />

      <AsyncState isLoading={isLoading} error={error}>
        <Table.ScrollContainer minWidth={640}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>ID</Table.Th>
                <Table.Th>Active</Table.Th>
                <Table.Th>Updated</Table.Th>
                <Table.Th w={100} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.map((c) => (
                <Table.Tr key={c.id}>
                  <Table.Td>{c.name || <Text c="dimmed">(unnamed)</Text>}</Table.Td>
                  <Table.Td>
                    <Badge variant="light">{c.id}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Switch
                      checked={c.is_active}
                      onChange={() => toggleActive(c)}
                      aria-label="Toggle active"
                    />
                  </Table.Td>
                  <Table.Td>{new Date(c.updated_at).toLocaleString()}</Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end">
                      <ActionIcon
                        variant="subtle"
                        onClick={() => navigate(`/platform/agent-configs/${c.id}`)}
                      >
                        <IconEdit size={16} />
                      </ActionIcon>
                      <ActionIcon variant="subtle" color="red" onClick={() => remove(c)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
              {data?.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={5} ta="center" c="dimmed">
                    No agent configs yet.
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </AsyncState>
    </>
  );
}
