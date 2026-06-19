import { AppShell, Burger, Group, NavLink, ScrollArea, Text } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconBuildingStore,
  IconFileUpload,
  IconLayoutDashboard,
  IconRobot,
  IconSettings,
  IconToolsKitchen2,
} from '@tabler/icons-react';
import { NavLink as RouterNavLink, Outlet, useLocation } from 'react-router-dom';

const NAV = [
  { to: '/admin', label: 'Dashboard', icon: IconLayoutDashboard, end: true },
  { to: '/admin/menu', label: 'Menu', icon: IconToolsKitchen2 },
  { to: '/admin/documents', label: 'Documents', icon: IconFileUpload },
  { to: '/admin/agent-configs', label: 'Agent configs', icon: IconRobot },
  { to: '/admin/parser-config', label: 'Parser config', icon: IconSettings },
  { to: '/admin/branches', label: 'Branches', icon: IconBuildingStore },
];

export function AdminLayout() {
  const [opened, { toggle, close }] = useDisclosure();
  const { pathname } = useLocation();

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" gap="sm">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
          <Text fw={700} size="lg">
            🍔 Drive-Thru Admin
          </Text>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        <ScrollArea>
          {NAV.map((item) => {
            const active = item.end ? pathname === item.to : pathname.startsWith(item.to);
            return (
              <NavLink
                key={item.to}
                component={RouterNavLink}
                to={item.to}
                end={item.end}
                label={item.label}
                leftSection={<item.icon size={18} stroke={1.5} />}
                active={active}
                onClick={close}
              />
            );
          })}
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
