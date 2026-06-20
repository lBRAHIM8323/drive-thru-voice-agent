import { useState } from 'react';
import {
  Accordion,
  Anchor,
  Badge,
  Group,
  Modal,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';


import { useBranches, useSession, useSessions } from '../../api/hooks';
import { AsyncState } from '../../components/AsyncState';
import { PageHeader } from '../../components/PageHeader';
import type { SessionRead } from '../../api/types';

function SessionDetailModal({
  sessionId,
  opened,
  onClose,
}: {
  sessionId: string;
  opened: boolean;
  onClose: () => void;
}) {
  const { data: session, isLoading, error } = useSession(sessionId);

  return (
    <Modal opened={opened} onClose={onClose} title="Session details" size="lg">
      <AsyncState isLoading={isLoading} error={error}>
        {session && <SessionDetailContent session={session} />}
      </AsyncState>
    </Modal>
  );
}

function SessionDetailContent({ session }: { session: SessionRead }) {
  return (
    <Stack>
      <Group gap="xs">
        <Text size="sm" c="dimmed">Status:</Text>
        <Badge color={session.status === 'active' ? 'green' : 'gray'}>{session.status}</Badge>
      </Group>
      {session.room_name && (
        <Group gap="xs">
          <Text size="sm" c="dimmed">Room:</Text>
          <Text size="sm">{session.room_name}</Text>
        </Group>
      )}
      {session.started_at && (
        <Group gap="xs">
          <Text size="sm" c="dimmed">Started:</Text>
          <Text size="sm">{new Date(session.started_at).toLocaleString()}</Text>
        </Group>
      )}
      {session.ended_at && (
        <Group gap="xs">
          <Text size="sm" c="dimmed">Ended:</Text>
          <Text size="sm">{new Date(session.ended_at).toLocaleString()}</Text>
        </Group>
      )}

      {session.audio_url && (
        <>
          <Title order={5} mt="sm">Recording</Title>
          <audio controls src={session.audio_url} style={{ width: '100%' }} />
        </>
      )}

      {session.transcript && (
        <>
          <Title order={5} mt="sm">Transcript</Title>
          <Text size="sm" style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
            {JSON.stringify(session.transcript, null, 2)}
          </Text>
        </>
      )}

      {session.orders.length > 0 && (
        <>
          <Title order={5} mt="sm">Orders</Title>
          {session.orders.map((order) => (
            <Accordion key={order.id}>
              <Accordion.Item value={order.id}>
                <Accordion.Control>
                  <Group gap="xs">
                    <Badge color={order.status === 'confirmed' ? 'green' : 'yellow'}>
                      {order.status}
                    </Badge>
                    <Text size="sm">
                      {order.currency} {order.total.toFixed(2)}
                    </Text>
                    {order.placed_at && (
                      <Text size="xs" c="dimmed">
                        {new Date(order.placed_at).toLocaleString()}
                      </Text>
                    )}
                  </Group>
                </Accordion.Control>
                <Accordion.Panel>
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Item</Table.Th>
                        <Table.Th>Size</Table.Th>
                        <Table.Th>Qty</Table.Th>
                        <Table.Th>Price</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {order.items.map((item) => (
                        <Table.Tr key={item.id}>
                          <Table.Td>{item.name_snapshot}</Table.Td>
                          <Table.Td>{item.size ?? '-'}</Table.Td>
                          <Table.Td>{item.quantity}</Table.Td>
                          <Table.Td>{item.total_price.toFixed(2)}</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                  <Group gap="xs" mt="xs">
                    <Text size="xs" c="dimmed">Subtotal:</Text>
                    <Text size="xs">{order.subtotal.toFixed(2)}</Text>
                    <Text size="xs" c="dimmed">Tax:</Text>
                    <Text size="xs">{order.tax.toFixed(2)}</Text>
                    <Text size="xs" fw={500}>Total: {order.total.toFixed(2)}</Text>
                  </Group>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          ))}
        </>
      )}
    </Stack>
  );
}

export function ListenInPage() {
  const { data: sessions, isLoading, error } = useSessions();
  const { data: branches } = useBranches();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [opened, { open, close }] = useDisclosure(false);

  function openDetail(id: string) {
    setSelectedId(id);
    open();
  }

  function handleClose() {
    setSelectedId(null);
    close();
  }

  return (
    <>
      <PageHeader
        title="Listen In"
        description="Review session recordings and transcripts."
      />

      <AsyncState isLoading={isLoading} error={error}>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Branch</Table.Th>
              <Table.Th>Room</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Started</Table.Th>
              <Table.Th>Ended</Table.Th>
              <Table.Th w={80} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sessions?.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={6}>
                  <Text c="dimmed" ta="center" py="xl">
                    No sessions yet.
                  </Text>
                </Table.Td>
              </Table.Tr>
            )}
            {sessions?.map((s) => (
              <Table.Tr key={s.id}>
                <Table.Td>
                  {branches?.find((b) => b.id === s.branch_id)?.name ?? '-'}
                </Table.Td>
                <Table.Td>{s.room_name ?? '-'}</Table.Td>
                <Table.Td>
                  <Badge color={s.status === 'active' ? 'green' : 'gray'}>
                    {s.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {s.started_at ? new Date(s.started_at).toLocaleString() : '-'}
                </Table.Td>
                <Table.Td>
                  {s.ended_at ? new Date(s.ended_at).toLocaleString() : '-'}
                </Table.Td>
                <Table.Td>
                  <Anchor
                    component="button"
                    onClick={() => openDetail(s.id)}
                    c="blue"
                    underline="hover"
                  >
                    View
                  </Anchor>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </AsyncState>

      {selectedId && (
        <SessionDetailModal
          sessionId={selectedId}
          opened={opened}
          onClose={handleClose}
        />
      )}
    </>
  );
}
