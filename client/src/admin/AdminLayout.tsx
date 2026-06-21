import {
  AppShell,
  Burger,
  Button,
  Group,
  Menu,
  NavLink,
  ScrollArea,
  Text,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconBuildingStore,
  IconHeadphones,
  IconFileUpload,
  IconLayoutDashboard,
  IconLogout,
  IconRobot,
  IconSettings,
  IconToolsKitchen2,
  IconUsers,
  IconUserCircle,
} from '@tabler/icons-react';
import { NavLink as RouterNavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../components/auth/AuthContext';

const ALL_NAV = [
  { to: '/platform', label: 'Dashboard', icon: IconLayoutDashboard, end: true, roles: ['admin', 'manager', 'staff'] },
  { to: '/platform/menu', label: 'Menu', icon: IconToolsKitchen2, roles: ['admin', 'manager', 'staff'] },
  { to: '/platform/listen', label: 'Listen in', icon: IconHeadphones, roles: ['admin', 'manager', 'staff'] },
  { to: '/platform/documents', label: 'Documents', icon: IconFileUpload, roles: ['admin', 'manager'] },
  { to: '/platform/agent-configs', label: 'Agent configs', icon: IconRobot, roles: ['admin', 'manager'] },
  { to: '/platform/parser-config', label: 'Parser config', icon: IconSettings, roles: ['admin'] },
  { to: '/platform/branches', label: 'Branches', icon: IconBuildingStore, roles: ['admin'] },
  { to: '/platform/users', label: 'Users', icon: IconUsers, roles: ['admin'] },
];

export function AdminLayout() {
  const [opened, { toggle, close }] = useDisclosure();
  const { pathname } = useLocation();
  const { user, logout } = useAuth();

  const navItems = ALL_NAV.filter((item) => item.roles.includes(user?.role ?? 'staff'));

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" gap="sm" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Text fw={700} size="lg">
              Drive-Thru Admin
            </Text>
          </Group>
          <Menu shadow="md" width={200}>
            <Menu.Target>
              <Button
                variant="subtle"
                leftSection={<IconUserCircle size={18} />}
                size="sm"
              >
                {user?.username ?? 'User'}
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item disabled>
                {user?.role} · {user?.email ?? 'no email'}
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item
                color="red"
                leftSection={<IconLogout size={16} />}
                onClick={logout}
              >
                Sign out
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        <ScrollArea>
          {navItems.map((item) => {
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
