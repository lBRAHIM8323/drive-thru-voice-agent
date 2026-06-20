import { useState } from 'react';
import {
  ActionIcon,
  Button,
  Group,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Table,
  TextInput,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconPencil, IconPlus, IconTrash } from '@tabler/icons-react';

import { useBranches, useCreateUser, useDeleteUser, useUpdateUser, useUsers } from '../../api/hooks';
import { PageHeader } from '../../components/PageHeader';
import { confirmDelete } from '../../components/confirmDelete';
import type { UserCreate, UserUpdate } from '../../api/types';

export function UsersPage() {
  const { data: users, isLoading } = useUsers();
  const { data: branches } = useBranches();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();

  const [opened, { open, close }] = useDisclosure(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<string>('staff');
  const [branchId, setBranchId] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(true);

  function resetForm() {
    setEditingId(null);
    setUsername('');
    setPassword('');
    setEmail('');
    setRole('staff');
    setBranchId(null);
    setIsActive(true);
  }

  function openCreate() {
    resetForm();
    open();
  }

  function openEdit(u: typeof users extends (infer U)[] ? U : never) {
    setEditingId(u.id);
    setUsername(u.username);
    setPassword('');
    setEmail(u.email ?? '');
    setRole(u.role);
    setBranchId(u.branch_id);
    setIsActive(u.is_active);
    open();
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (editingId) {
      const body: UserUpdate = {};
      if (password) body.password = password;
      if (email !== '') body.email = email;
      if (role) body.role = role as UserUpdate['role'];
      body.branch_id = branchId;
      body.is_active = isActive;
      await updateUser.mutateAsync({ id: editingId, body });
    } else {
      await createUser.mutateAsync({
        username,
        password,
        email: email || undefined,
        role: role as UserCreate['role'],
        branch_id: branchId,
        is_active: isActive,
      });
    }
    close();
    resetForm();
  }

  async function handleDelete(id: string, username: string) {
    if (!(await confirmDelete(`Delete user "${username}"?`))) return;
    await deleteUser.mutateAsync(id);
  }

  const branchOptions = (branches ?? []).map((b) => ({
    value: b.id,
    label: b.name,
  }));

  return (
    <>
      <PageHeader
        title="Users"
        actions={
          <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
            Add user
          </Button>
        }
      />

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Username</Table.Th>
            <Table.Th>Email</Table.Th>
            <Table.Th>Role</Table.Th>
            <Table.Th>Branch</Table.Th>
            <Table.Th>Active</Table.Th>
            <Table.Th w={80}>Actions</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {isLoading && (
            <Table.Tr>
              <Table.Td colSpan={6}>Loading...</Table.Td>
            </Table.Tr>
          )}
          {users?.map((u) => (
            <Table.Tr key={u.id}>
              <Table.Td>{u.username}</Table.Td>
              <Table.Td>{u.email ?? '-'}</Table.Td>
              <Table.Td>{u.role}</Table.Td>
              <Table.Td>
                {branches?.find((b) => b.id === u.branch_id)?.name ?? '-'}
              </Table.Td>
              <Table.Td>{u.is_active ? 'Yes' : 'No'}</Table.Td>
              <Table.Td>
                <Group gap="xs">
                  <ActionIcon variant="subtle" onClick={() => openEdit(u)}>
                    <IconPencil size={16} />
                  </ActionIcon>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    onClick={() => handleDelete(u.id, u.username)}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Modal
        opened={opened}
        onClose={close}
        title={editingId ? 'Edit user' : 'Create user'}
        size="md"
      >
        <form onSubmit={handleSave}>
          <Stack>
            <TextInput
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.currentTarget.value)}
              required
              disabled={!!editingId}
            />
            <TextInput
              label="Email"
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
            />
            <PasswordInput
              label={editingId ? 'New password (leave blank to keep)' : 'Password'}
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              required={!editingId}
            />
            <Select
              label="Role"
              value={role}
              onChange={(v) => setRole(v ?? 'staff')}
              data={[
                { value: 'admin', label: 'Admin' },
                { value: 'manager', label: 'Manager' },
                { value: 'staff', label: 'Staff' },
              ]}
            />
            <Select
              label="Branch"
              value={branchId}
              onChange={setBranchId}
              data={[{ value: '', label: 'None' }, ...branchOptions]}
              clearable
            />
            <Switch
              label="Active"
              checked={isActive}
              onChange={(e) => setIsActive(e.currentTarget.checked)}
            />
            <Group justify="flex-end" mt="md">
              <Button variant="default" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" loading={createUser.isPending || updateUser.isPending}>
                {editingId ? 'Save' : 'Create'}
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>
    </>
  );
}
