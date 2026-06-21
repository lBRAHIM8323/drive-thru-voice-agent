import { useEffect, useMemo, useState } from 'react';
import { Badge, Divider, Group, Image, Paper, Stack, Text, Title } from '@mantine/core';
import { IconBooks, IconStarFilled, IconToolsKitchen2 } from '@tabler/icons-react';
import { useRoomContext } from '@livekit/components-react';

import type { MenuItem, MenuPayload } from '../api/types';

function money(currency: string, amount: number) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function offerIsLive(item: MenuItem): boolean {
  if (item.offer_price == null) return false;
  if (!item.offer_until) return true;
  return new Date(item.offer_until).getTime() >= Date.now();
}

const dietaryColor: Record<string, string> = { veg: 'green', non_veg: 'red', vegan: 'teal' };
const dietaryLabel: Record<string, string> = { veg: 'Veg', non_veg: 'Non-veg', vegan: 'Vegan' };

function priceLabel(item: MenuItem): string {
  if (item.sizes.length > 0) {
    return item.sizes.map((s) => `${s.size} ${money(item.currency, s.price)}`).join(' / ');
  }
  if (offerIsLive(item) && item.offer_price != null) {
    return money(item.currency, item.offer_price);
  }
  if (item.price != null) {
    return money(item.currency, item.price);
  }
  return '';
}

export function MenuPanel() {
  const room = useRoomContext();
  const [menu, setMenu] = useState<MenuPayload | null>(null);

  useEffect(() => {
    const lp = room.localParticipant;
    const handler = async (data: { payload: string }) => {
      try {
        setMenu(JSON.parse(data.payload) as MenuPayload);
      } catch {
        /* ignore malformed payloads */
      }
      return 'ok';
    };
    lp.registerRpcMethod('set_menu_content', handler);
    return () => lp.unregisterRpcMethod('set_menu_content');
  }, [room]);

  const grouped = useMemo(() => {
    if (!menu) return [];
    const map = new Map<string, MenuItem[]>();
    for (const item of menu.items) {
      const cat = item.category || 'Other';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(item);
    }
    return Array.from(map.entries());
  }, [menu]);

  return (
    <Stack h="100%" gap={0}>
      <Group gap="xs" p="md">
        <IconBooks size={20} />
        <Text fw={700} size="lg">
          Menu
        </Text>
      </Group>
      <Divider />

      <Stack gap="lg" p="md" style={{ flex: 1, overflowY: 'auto' }}>
        {!menu && (
          <Text c="dimmed" ta="center" mt="xl">
            Loading menu…
          </Text>
        )}
        {menu && grouped.length === 0 && (
          <Text c="dimmed" ta="center" mt="xl">
            No items on the menu.
          </Text>
        )}
        {grouped.map(([category, items]) => (
          <Stack key={category} gap="xs">
            <Title order={5} tt="capitalize">
              {category}
            </Title>
            {items.map((item) => (
              <Paper key={item.id} withBorder p="sm" radius="md" opacity={item.available ? 1 : 0.5}>
                <Group wrap="nowrap" align="flex-start">
                  {item.image_url ? (
                    <Image src={item.image_url} w={40} h={40} radius="sm" alt={item.name} />
                  ) : (
                    <Group w={40} h={40} justify="center" align="center" bg="var(--mantine-color-default-hover)" style={{ borderRadius: 8 }}>
                      <IconToolsKitchen2 size={18} opacity={0.5} />
                    </Group>
                  )}
                  <Stack gap={2} style={{ flex: 1 }}>
                    <Group justify="space-between" wrap="nowrap" gap="xs">
                      <Group gap={4} wrap="nowrap" style={{ minWidth: 0 }}>
                        <Text fw={500} size="sm" lineClamp={1}>
                          {item.name}
                        </Text>
                        {item.is_favorite && <IconStarFilled size={12} color="var(--mantine-color-yellow-6)" />}
                      </Group>
                      <Group gap={4} wrap="nowrap" style={{ whiteSpace: 'nowrap' }}>
                        {offerIsLive(item) && item.price != null && item.offer_price != null && (
                          <Text size="xs" c="dimmed" td="line-through">
                            {money(item.currency, item.price)}
                          </Text>
                        )}
                        <Text size="xs" c={offerIsLive(item) ? 'orange.6' : 'dimmed'} fw={offerIsLive(item) ? 600 : 400}>
                          {priceLabel(item)}
                        </Text>
                      </Group>
                    </Group>
                    {item.description && (
                      <Text size="xs" c="dimmed" lineClamp={2}>
                        {item.description}
                      </Text>
                    )}
                    <Group gap="xs">
                      {item.dietary && (
                        <Badge size="xs" variant="light" color={dietaryColor[item.dietary] ?? 'gray'}>
                          {dietaryLabel[item.dietary] ?? item.dietary}
                        </Badge>
                      )}
                      {offerIsLive(item) && (
                        <Badge size="xs" color="orange">
                          Offer
                        </Badge>
                      )}
                      {item.serves != null && (
                        <Badge size="xs" variant="light" color="grape">
                          Serves {item.serves}
                        </Badge>
                      )}
                      {(item.tags ?? []).map((t) => (
                        <Badge key={t} size="xs" variant="outline" color="gray">
                          {t.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                      {item.calories != null && (
                        <Badge size="xs" variant="light" color="gray">
                          {item.calories} Cal
                        </Badge>
                      )}
                      {!item.available && (
                        <Badge size="xs" color="red">
                          Unavailable
                        </Badge>
                      )}
                    </Group>
                  </Stack>
                </Group>
              </Paper>
            ))}
          </Stack>
        ))}
      </Stack>
    </Stack>
  );
}
