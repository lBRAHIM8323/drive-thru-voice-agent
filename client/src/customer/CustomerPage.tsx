import { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Center, Flex, Paper, Stack, Text, Title } from '@mantine/core';
import { IconHeadset, IconMicrophone } from '@tabler/icons-react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useRoomContext,
  useVoiceAssistant,
  VoiceAssistantControlBar,
  type AgentState,
} from '@livekit/components-react';

import { useCreateConnection } from '../api/hooks';
import type { ConnectionInfo, UIConfig } from '../api/types';
import { notifyError } from '../lib/notify';
import { AgentVisualizer } from './Visualizers';
import { CartPanel } from './CartPanel';
import { MenuPanel } from './MenuPanel';
import { useWakeWord } from './useWakeWord';

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

  const start = useCallback(async () => {
    try {
      setInfo(await connect.mutateAsync(undefined));
    } catch (e) {
      notifyError(e);
    }
  }, [connect]);

  if (!info) {
    return <PreConnectionView connect={connect} onConnect={start} />;
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

interface PreConnectionConfig {
  ui: UIConfig;
  wakewords: import('../api/types').WakeWordConfig | null;
}

function PreConnectionView({
  connect,
  onConnect,
}: {
  connect: { isPending: boolean };
  onConnect: () => void;
}) {
  const [bootConfig, setBootConfig] = useState<PreConnectionConfig | null>(null);

  const { listening, error: wwError, supported } = useWakeWord({
    config: bootConfig?.wakewords ?? { enabled: false, phrases: [], threshold: 0.5, model_url: '' },
    onDetected: onConnect,
  });

  const wakewordsOn = (bootConfig?.wakewords?.enabled && (bootConfig?.wakewords?.phrases?.length ?? 0) > 0) ?? false;

  // Lightweight GET — no session created.
  useEffect(() => {
    if (bootConfig) return;
    (async () => {
      try {
        const res = await fetch('/agent/connection/config');
        if (res.ok) setBootConfig(await res.json() as PreConnectionConfig);
      } catch {
        // fall back to button
      }
    })();
  }, [bootConfig]);

  if (!bootConfig && !wakewordsOn) {
    return (
      <Center h="100vh">
        <Stack align="center" gap="lg">
          <Title order={1}>🍔 Drive-Thru</Title>
          <Text c="dimmed">Tap below and start ordering by voice.</Text>
          <Button size="lg" radius="xl" onClick={onConnect} loading={connect.isPending}>
            Start order
          </Button>
        </Stack>
      </Center>
    );
  }

  return (
    <Center h="100vh">
      <Stack align="center" gap="lg">
        <Title order={1}>🍔 Drive-Thru</Title>
        {wakewordsOn && supported && bootConfig && (
          <>
            <IconMicrophone
              size={48}
              opacity={listening ? 1 : 0.4}
              style={{
                transition: 'opacity 0.3s',
              }}
            />
            <Text c={listening ? 'blue' : 'dimmed'} fw={listening ? 600 : 400}>
              {listening
                ? `Say "${bootConfig.wakewords?.phrases[0] ?? 'hey livekit'}" to start…`
                : wwError ?? 'Initialising…'}
            </Text>
          </>
        )}
        {(!wakewordsOn || !supported) && (
          <Text c="dimmed">Tap below and start ordering by voice.</Text>
        )}
        {wwError && (
          <Text c="dimmed" size="sm">
            Wake word unavailable — use the button instead.
          </Text>
        )}
        <Button size="lg" radius="xl" onClick={onConnect} loading={connect.isPending}>
          {wakewordsOn ? 'Tap to order' : 'Start order'}
        </Button>
      </Stack>
    </Center>
  );
}

function SessionView({ ui }: { ui: UIConfig }) {
  const { state, audioTrack } = useVoiceAssistant();
  const room = useRoomContext();
  const [transferring, setTransferring] = useState(false);
  const accent = ui.accent_color ?? undefined;

  // The agent calls `set_transfer_state` over RPC when handing off to a human.
  useEffect(() => {
    const lp = room.localParticipant;
    const handler = async (data: { payload: string }) => {
      try {
        const { state: s } = JSON.parse(data.payload) as { state?: string };
        setTransferring(s === 'connecting');
      } catch {
        /* ignore malformed payloads */
      }
      return 'ok';
    };
    lp.registerRpcMethod('set_transfer_state', handler);
    return () => lp.unregisterRpcMethod('set_transfer_state');
  }, [room]);

  return (
    <Flex h="100vh">
      <Paper
        w={320}
        radius={0}
        style={{ borderRight: '1px solid var(--mantine-color-default-border)' }}
      >
        <MenuPanel />
      </Paper>

      <Stack flex={1} p="xl" justify="space-between" align="stretch" mih={0}>
        <Title order={3} ta="center">
          {ui.title ?? 'Welcome — how can I help?'}
        </Title>

        {transferring && (
          <Alert
            icon={<IconHeadset size={18} />}
            color="orange"
            variant="light"
            title="Connecting you to a team member"
          >
            Please hold for a moment while we transfer your call.
          </Alert>
        )}

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
