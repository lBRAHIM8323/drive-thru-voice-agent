import { useEffect, useState } from 'react';
import { Badge, Divider, Group, Image, Paper, Stack, Text } from '@mantine/core';
import { IconShoppingCart, IconToolsKitchen2 } from '@tabler/icons-react';
import { useRoomContext } from '@livekit/components-react';

import type { CartPayload } from '../api/types';

function money(currency: string, amount: number) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

export function CartPanel() {
  const room = useRoomContext();
  const [cart, setCart] = useState<CartPayload | null>(null);

  useEffect(() => {
    const lp = room.localParticipant;
    // The voice-agent pushes the current order here whenever it changes.
    const handler = async (data: { payload: string }) => {
      try {
        setCart(JSON.parse(data.payload) as CartPayload);
      } catch {
        /* ignore malformed payloads */
      }
      return 'ok';
    };
    lp.registerRpcMethod('set_cart_content', handler);
    return () => lp.unregisterRpcMethod('set_cart_content');
  }, [room]);

  const currency = cart?.currency ?? 'USD';
  const items = cart?.items ?? [];

  return (
    <Stack h="100%" gap={0}>
      <Group gap="xs" p="md">
        <IconShoppingCart size={20} />
        <Text fw={700} size="lg">
          Your order
        </Text>
      </Group>
      <Divider />

      <Stack gap="sm" p="md" style={{ flex: 1, overflowY: 'auto' }}>
        {items.length === 0 && (
          <Text c="dimmed" ta="center" mt="xl">
            Your order will appear here as you speak.
          </Text>
        )}
        {items.map((item, i) => (
          <Paper key={i} withBorder p="sm" radius="md">
            <Group wrap="nowrap" align="flex-start">
              {item.image_url ? (
                <Image src={item.image_url} w={48} h={48} radius="sm" alt={item.name} />
              ) : (
                <Group w={48} h={48} justify="center" align="center" bg="var(--mantine-color-default-hover)" style={{ borderRadius: 8 }}>
                  <IconToolsKitchen2 size={22} opacity={0.5} />
                </Group>
              )}
              <Stack gap={2} style={{ flex: 1 }}>
                <Group justify="space-between" wrap="nowrap">
                  <Text fw={500}>{item.name}</Text>
                  <Text fw={500}>{money(currency, item.line_total)}</Text>
                </Group>
                {item.details && (
                  <Text size="xs" c="dimmed">
                    {item.details}
                  </Text>
                )}
                <Group gap="xs">
                  <Badge size="sm" variant="light">
                    ×{item.quantity}
                  </Badge>
                  <Text size="xs" c="dimmed">
                    {money(currency, item.unit_price)} each
                  </Text>
                </Group>
              </Stack>
            </Group>
          </Paper>
        ))}
      </Stack>

      <Divider />
      <Group justify="space-between" p="md">
        <Text fw={700}>Total</Text>
        <Text fw={700} size="lg">
          {money(currency, cart?.total ?? 0)}
        </Text>
      </Group>
    </Stack>
  );
}
