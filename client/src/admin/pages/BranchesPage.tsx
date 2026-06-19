import { useState } from 'react';
import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Modal,
  Switch,
  Table,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconEdit, IconPlus, IconTrash } from '@tabler/icons-react';

import {
  useBranches,
  useCreateBranch,
  useDeleteBranch,
  useUpdateBranch,
} from '../../api/hooks';
import type { Branch } from '../../api/types';
import { AsyncState } from '../../components/AsyncState';
import { PageHeader } from '../../components/PageHeader';
import { confirmDelete } from '../../components/confirmDelete';
import { notifyError, notifySuccess } from '../../lib/notify';

interface BranchFormValues {
  name: string;
  city: string;
  country: string;
  currency: string;
  timezone: string;
  phone: string;
  is_active: boolean;
}

export function BranchesPage() {
  const { data, isLoading, error } = useBranches();
  const createMut = useCreateBranch();
  const updateMut = useUpdateBranch();
  const deleteMut = useDeleteBranch();

  const [editing, setEditing] = useState<Branch | null>(null);
  const [opened, setOpened] = useState(false);

  const form = useForm<BranchFormValues>({
    initialValues: {
      name: '',
      city: '',
      country: '',
      currency: 'USD',
      timezone: 'UTC',
      phone: '',
      is_active: true,
    },
    validate: { name: (v) => (v.trim() ? null : 'Name is required') },
  });

  function openCreate() {
    setEditing(null);
    form.setValues({
      name: '',
      city: '',
      country: '',
      currency: 'USD',
      timezone: 'UTC',
      phone: '',
      is_active: true,
    });
    setOpened(true);
  }

  function openEdit(b: Branch) {
    setEditing(b);
    form.setValues({
      name: b.name,
      city: b.city ?? '',
      country: b.country ?? '',
      currency: b.currency,
      timezone: b.timezone,
      phone: b.phone ?? '',
      is_active: b.is_active,
    });
    setOpened(true);
  }

  async function submit(values: BranchFormValues) {
    try {
      if (editing) {
        await updateMut.mutateAsync({ id: editing.id, body: values });
        notifySuccess('Branch updated');
      } else {
        await createMut.mutateAsync(values);
        notifySuccess('Branch created');
      }
      setOpened(false);
    } catch (e) {
      notifyError(e);
    }
  }

  async function remove(b: Branch) {
    if (!(await confirmDelete(`Delete branch "${b.name}"?`))) return;
    try {
      await deleteMut.mutateAsync(b.id);
      notifySuccess('Branch deleted');
    } catch (e) {
      notifyError(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Branches"
        description="Franchise locations. Menu items and agent configs can be scoped to a branch."
        actions={
          <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
            New branch
          </Button>
        }
      />

      <AsyncState isLoading={isLoading} error={error}>
        <Table.ScrollContainer minWidth={600}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Slug</Table.Th>
                <Table.Th>Location</Table.Th>
                <Table.Th>Currency</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th w={100} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.map((b) => (
                <Table.Tr key={b.id}>
                  <Table.Td>{b.name}</Table.Td>
                  <Table.Td>
                    <Badge variant="light">{b.slug}</Badge>
                  </Table.Td>
                  <Table.Td>{[b.city, b.country].filter(Boolean).join(', ') || '—'}</Table.Td>
                  <Table.Td>{b.currency}</Table.Td>
                  <Table.Td>
                    <Badge color={b.is_active ? 'green' : 'gray'} variant="light">
                      {b.is_active ? 'active' : 'inactive'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end">
                      <ActionIcon variant="subtle" onClick={() => openEdit(b)}>
                        <IconEdit size={16} />
                      </ActionIcon>
                      <ActionIcon variant="subtle" color="red" onClick={() => remove(b)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
              {data?.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={6} ta="center" c="dimmed">
                    No branches yet.
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </AsyncState>

      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={editing ? 'Edit branch' : 'New branch'}
      >
        <form onSubmit={form.onSubmit(submit)}>
          <TextInput label="Name" withAsterisk {...form.getInputProps('name')} />
          <Group grow mt="sm">
            <TextInput label="City" {...form.getInputProps('city')} />
            <TextInput label="Country" {...form.getInputProps('country')} />
          </Group>
          <Group grow mt="sm">
            <TextInput label="Currency" {...form.getInputProps('currency')} />
            <TextInput label="Timezone" {...form.getInputProps('timezone')} />
          </Group>
          <TextInput label="Phone" mt="sm" {...form.getInputProps('phone')} />
          <Switch
            label="Active"
            mt="md"
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />
          <Group justify="flex-end" mt="lg">
            <Button variant="default" onClick={() => setOpened(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={createMut.isPending || updateMut.isPending}>
              {editing ? 'Save' : 'Create'}
            </Button>
          </Group>
        </form>
      </Modal>
    </>
  );
}
