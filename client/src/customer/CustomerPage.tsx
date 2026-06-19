import { useState } from 'react';
import { Badge, Button, Center, Flex, Paper, Stack, Text, Title } from '@mantine/core';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VoiceAssistantControlBar,
  useVoiceAssistant,
  type AgentState,
} from '@livekit/components-react';

import { useCreateConnection } from '../api/hooks';
import type { ConnectionInfo, UIConfig } from '../api/types';
import { notifyError } from '../lib/notify';
import { AgentVisualizer } from './Visualizers';
import { CartPanel } from './CartPanel';

const STATE_LABEL: Partial<Record<AgentState, string>> = {
  disconnected: 'Disconnected',
  connecting: 'Connecting…',
  initializing: 'Getting ready…',
  listening: 'Listening',
  thinking: 'Thinking…',
  speaking: 'Speaking',
};

export function CustomerPage() {
  const connect = useCreateConnection();
  const [info, setInfo] = useState<ConnectionInfo | null>(null);

  async function start() {
    try {
      setInfo(await connect.mutateAsync(undefined));
    } catch (e) {
      notifyError(e);
    }
  }

  if (!info) {
    return (
      <Center h="100vh">
        <Stack align="center" gap="lg">
          <Title order={1}>🍔 Drive-Thru</Title>
          <Text c="dimmed">Tap below and start ordering by voice.</Text>
          <Button size="lg" radius="xl" onClick={start} loading={connect.isPending}>
            Start order
          </Button>
        </Stack>
      </Center>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={info.server_url}
      token={info.token}
      connect
      audio
      video={false}
      onDisconnected={() => setInfo(null)}
      style={{ height: '100vh' }}
    >
      <SessionView ui={info.ui} />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function SessionView({ ui }: { ui: UIConfig }) {
  const { state, audioTrack } = useVoiceAssistant();
  const accent = ui.accent_color ?? undefined;

  return (
    <Flex h="100vh">
      <Stack flex={1} p="xl" justify="space-between" align="stretch" mih={0}>
        <Title order={3} ta="center">
          {ui.title ?? 'Welcome — how can I help?'}
        </Title>

        <Center style={{ flex: 1 }}>
          <Stack align="center" gap="md">
            <AgentVisualizer
              variant={ui.visualizer}
              audioTrack={audioTrack}
              state={state}
              accentColor={accent}
            />
            <Badge size="lg" variant="light" color={accent ? undefined : 'blue'}>
              {STATE_LABEL[state] ?? state}
            </Badge>
          </Stack>
        </Center>

        <Center>
          <VoiceAssistantControlBar />
        </Center>
      </Stack>

      <Paper
        w={380}
        radius={0}
        style={{ borderLeft: '1px solid var(--mantine-color-default-border)' }}
      >
        <CartPanel />
      </Paper>
    </Flex>
  );
}
