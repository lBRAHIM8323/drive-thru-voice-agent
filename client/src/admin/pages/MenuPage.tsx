import { useMemo, useState } from 'react';
import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Modal,
  NumberInput,
  Select,
  Switch,
  Table,
  TagsInput,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconEdit, IconPlus, IconStar, IconTrash } from '@tabler/icons-react';

import {
  useBranches,
  useCreateMenuItem,
  useDeleteMenuItem,
  useMenu,
  useUpdateMenuItem,
  type MenuFilters,
} from '../../api/hooks';
import type { Dietary, ItemSize, MenuItem } from '../../api/types';
import { AsyncState } from '../../components/AsyncState';
import { PageHeader } from '../../components/PageHeader';
import { TriStateSelect } from '../../components/TriStateSelect';
import { confirmDelete } from '../../components/confirmDelete';
import { notifyError, notifySuccess } from '../../lib/notify';
import { dietaryOptions, itemSizes, selectData, suggestedTags } from '../../lib/options';

const dietaryLabel: Record<Dietary, string> = {
  veg: 'Veg',
  non_veg: 'Non-veg',
  vegan: 'Vegan',
};
const dietaryColor: Record<Dietary, string> = {
  veg: 'green',
  non_veg: 'red',
  vegan: 'teal',
};

function offerIsLive(item: MenuItem): boolean {
  if (item.offer_price == null) return false;
  if (!item.offer_until) return true;
  return new Date(item.offer_until).getTime() >= Date.now();
}

type NumOrEmpty = number | '';

interface SizeRow {
  size: ItemSize;
  price: NumOrEmpty;
  calories: NumOrEmpty;
}

interface MenuFormValues {
  id: string;
  name: string;
  category: string;
  description: string;
  available: boolean;
  voice_alias: string;
  currency: string;
  branch_id: string | null;
  price: NumOrEmpty;
  calories: NumOrEmpty;
  dietary: string | null;
  tags: string[];
  serves: NumOrEmpty;
  is_favorite: boolean;
  offer_price: NumOrEmpty;
  offer_until: string; // datetime-local string, e.g. "2026-06-30T18:00"
  sizes: SizeRow[];
}

const emptyForm: MenuFormValues = {
  id: '',
  name: '',
  category: 'regular',
  description: '',
  available: true,
  voice_alias: '',
  currency: 'USD',
  branch_id: null,
  price: '',
  calories: '',
  dietary: null,
  tags: [],
  serves: '',
  is_favorite: false,
  offer_price: '',
  offer_until: '',
  sizes: [],
};

const nOrNull = (v: NumOrEmpty) => (v === '' ? null : Number(v));
const sOrNull = (v: string) => (v.trim() ? v.trim() : null);

export function MenuPage() {
  const [category, setCategory] = useState<string | null>(null);
  const [favorite, setFavorite] = useState<boolean | null>(null);
  const [onOffer, setOnOffer] = useState<boolean | null>(null);
  const filters: MenuFilters = {
    category: category ?? undefined,
    favorite: favorite ?? undefined,
    on_offer: onOffer ?? undefined,
  };
  const { data, isLoading, error } = useMenu(filters);
  const allItems = useMenu().data;
  const branches = useBranches();
  const createMut = useCreateMenuItem();
  const updateMut = useUpdateMenuItem();
  const deleteMut = useDeleteMenuItem();

  const [editing, setEditing] = useState<MenuItem | null>(null);
  const [opened, setOpened] = useState(false);

  const categories = useMemo(
    () => Array.from(new Set((allItems ?? []).map((i) => i.category))).sort(),
    [allItems],
  );

  const form = useForm<MenuFormValues>({
    initialValues: emptyForm,
    validate: {
      name: (v) => (v.trim() ? null : 'Name is required'),
      category: (v) => (v.trim() ? null : 'Category is required'),
    },
  });

  function openCreate() {
    setEditing(null);
    form.setValues(emptyForm);
    setOpened(true);
  }

  function openEdit(item: MenuItem) {
    setEditing(item);
    form.setValues({
      id: item.id,
      name: item.name,
      category: item.category,
      description: item.description ?? '',
      available: item.available,
      voice_alias: item.voice_alias ?? '',
      currency: item.currency,
      branch_id: item.branch_id,
      price: item.price ?? '',
      calories: item.calories ?? '',
      dietary: item.dietary,
      tags: item.tags ?? [],
      serves: item.serves ?? '',
      is_favorite: item.is_favorite,
      offer_price: item.offer_price ?? '',
      // ISO → "YYYY-MM-DDTHH:mm" for the native datetime-local input.
      offer_until: item.offer_until ? item.offer_until.slice(0, 16) : '',
      sizes: item.sizes.map((s) => ({
        size: s.size,
        price: s.price,
        calories: s.calories ?? '',
      })),
    });
    setOpened(true);
  }

  async function submit(values: MenuFormValues) {
    const payload = {
      name: values.name.trim(),
      category: values.category.trim(),
      description: sOrNull(values.description),
      available: values.available,
      voice_alias: sOrNull(values.voice_alias),
      image_url: null,
      currency: values.currency.trim() || 'USD',
      branch_id: values.branch_id,
      price: values.sizes.length ? null : nOrNull(values.price),
      calories: values.sizes.length ? null : nOrNull(values.calories),
      dietary: (values.dietary as Dietary | null) ?? null,
      tags: values.tags,
      serves: nOrNull(values.serves),
      is_favorite: values.is_favorite,
      offer_price: nOrNull(values.offer_price),
      offer_until: values.offer_until ? new Date(values.offer_until).toISOString() : null,
      sizes: values.sizes.map((s) => ({
        size: s.size,
        price: Number(s.price || 0),
        calories: nOrNull(s.calories),
      })),
    };
    try {
      if (editing) {
        await updateMut.mutateAsync({ id: editing.id, body: payload });
        notifySuccess('Item updated');
      } else {
        await createMut.mutateAsync({ ...payload, id: sOrNull(values.id) });
        notifySuccess('Item created');
      }
      setOpened(false);
    } catch (e) {
      notifyError(e);
    }
  }

  async function remove(item: MenuItem) {
    if (!(await confirmDelete(`Delete "${item.name}"?`))) return;
    try {
      await deleteMut.mutateAsync(item.id);
      notifySuccess('Item deleted');
    } catch (e) {
      notifyError(e);
    }
  }

  function priceLabel(item: MenuItem) {
    if (item.sizes.length) {
      return item.sizes.map((s) => `${s.size} ${s.price}`).join(' · ');
    }
    return item.price != null ? `${item.price}` : '—';
  }

  return (
    <>
      <PageHeader
        title="Menu"
        description="Items the agent can take orders for. Upload a menu document to bulk-import."
        actions={
          <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
            New item
          </Button>
        }
      />

      <Group mb="md">
        <Select
          placeholder="All categories"
          clearable
          data={selectData(categories)}
          value={category}
          onChange={setCategory}
          w={220}
        />
        <TriStateSelect
          label="Fav"
          value={favorite}
          onChange={setFavorite}
        />
        <TriStateSelect
          label="Offer"
          value={onOffer}
          onChange={setOnOffer}
        />
      </Group>

      <AsyncState isLoading={isLoading} error={error}>
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Category</Table.Th>
                <Table.Th>Dietary</Table.Th>
                <Table.Th>Price</Table.Th>
                <Table.Th>Available</Table.Th>
                <Table.Th w={100} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.map((item) => (
                <Table.Tr key={item.id}>
                  <Table.Td>
                    <Group gap={6} wrap="nowrap">
                      <Text fw={500}>{item.name}</Text>
                      {item.is_favorite && (
                        <IconStar size={14} fill="var(--mantine-color-yellow-5)" color="var(--mantine-color-yellow-6)" />
                      )}
                      {offerIsLive(item) && (
                        <Badge size="xs" color="orange" variant="light">
                          offer
                        </Badge>
                      )}
                    </Group>
                    <Text size="xs" c="dimmed">
                      {item.id}
                      {item.serves != null ? ` · serves ${item.serves}` : ''}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light">{item.category}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      {item.dietary && (
                        <Badge size="xs" variant="light" color={dietaryColor[item.dietary]}>
                          {dietaryLabel[item.dietary]}
                        </Badge>
                      )}
                      {(item.tags ?? []).map((t) => (
                        <Badge key={t} size="xs" variant="outline" color="gray">
                          {t.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                      {!item.dietary && (item.tags ?? []).length === 0 && (
                        <Text size="xs" c="dimmed">
                          —
                        </Text>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {offerIsLive(item) && item.offer_price != null ? (
                      <Group gap={6} wrap="nowrap">
                        <Text c="orange.7" fw={500}>
                          {item.currency} {item.offer_price}
                        </Text>
                        <Text size="xs" c="dimmed" td="line-through">
                          {priceLabel(item)}
                        </Text>
                      </Group>
                    ) : (
                      <>
                        {item.currency} {priceLabel(item)}
                      </>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Badge color={item.available ? 'green' : 'gray'} variant="light">
                      {item.available ? 'yes' : 'no'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end">
                      <ActionIcon variant="subtle" onClick={() => openEdit(item)}>
                        <IconEdit size={16} />
                      </ActionIcon>
                      <ActionIcon variant="subtle" color="red" onClick={() => remove(item)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
              {data?.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={6} ta="center" c="dimmed">
                    No items{category ? ' in this category' : ''} yet.
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
        title={editing ? `Edit ${editing.name}` : 'New menu item'}
        size="lg"
      >
        <form onSubmit={form.onSubmit(submit)}>
          <Group grow>
            <TextInput label="Name" withAsterisk {...form.getInputProps('name')} />
            <TextInput
              label="Category"
              withAsterisk
              placeholder="e.g. coffee, burgers, drinks"
              {...form.getInputProps('category')}
            />
          </Group>

          {!editing && (
            <TextInput
              label="ID (slug)"
              description="Leave blank to auto-generate from the name."
              mt="sm"
              {...form.getInputProps('id')}
            />
          )}

          <Textarea label="Description" mt="sm" autosize minRows={1} {...form.getInputProps('description')} />

          <Group grow mt="sm">
            <TextInput label="Currency" {...form.getInputProps('currency')} />
            <TextInput label="Voice alias" {...form.getInputProps('voice_alias')} />
            <Select
              label="Branch"
              placeholder="Global (all branches)"
              clearable
              data={(branches.data ?? []).map((b) => ({ value: b.id, label: b.name }))}
              {...form.getInputProps('branch_id')}
            />
          </Group>

          {form.values.sizes.length === 0 && (
            <Group grow mt="sm">
              <NumberInput label="Price" {...form.getInputProps('price')} />
              <NumberInput label="Calories" {...form.getInputProps('calories')} />
            </Group>
          )}

          <Group grow mt="sm">
            <Select
              label="Dietary"
              placeholder="Not specified"
              clearable
              data={dietaryOptions}
              {...form.getInputProps('dietary')}
            />
            <NumberInput
              label="Serves"
              description="People a meal feeds"
              min={1}
              {...form.getInputProps('serves')}
            />
          </Group>

          <TagsInput
            label="Dietary tags"
            description="e.g. lactose_free, gluten_free, halal. Press Enter to add."
            mt="sm"
            data={[...suggestedTags]}
            clearable
            {...form.getInputProps('tags')}
          />

          <Text fw={500} size="sm" mt="lg" mb="xs">
            Limited-time offer
          </Text>
          <Group grow>
            <NumberInput
              label="Offer price"
              description="Discounted price while the offer runs"
              min={0}
              decimalScale={2}
              {...form.getInputProps('offer_price')}
            />
            <TextInput
              label="Offer valid until"
              type="datetime-local"
              description="Leave blank for no end date"
              {...form.getInputProps('offer_until')}
            />
          </Group>

          <Switch
            label="Customer favourite"
            description="Surfaced by the agent for upsell suggestions"
            mt="md"
            {...form.getInputProps('is_favorite', { type: 'checkbox' })}
          />

          <Group justify="space-between" mt="lg" mb="xs">
            <Text fw={500} size="sm">
              Sizes
            </Text>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={14} />}
              onClick={() =>
                form.insertListItem('sizes', { size: 'M', price: '', calories: '' })
              }
            >
              Add size
            </Button>
          </Group>
          <Text size="xs" c="dimmed" mb="xs">
            Add sizes for size-selectable items (price per size). Otherwise use the single price above.
          </Text>

          {form.values.sizes.map((_, i) => (
            <Group key={i} mt="xs" align="flex-end">
              <Select
                label={i === 0 ? 'Size' : undefined}
                w={90}
                data={selectData(itemSizes)}
                {...form.getInputProps(`sizes.${i}.size`)}
              />
              <NumberInput
                label={i === 0 ? 'Price' : undefined}
                flex={1}
                {...form.getInputProps(`sizes.${i}.price`)}
              />
              <NumberInput
                label={i === 0 ? 'Calories' : undefined}
                flex={1}
                {...form.getInputProps(`sizes.${i}.calories`)}
              />
              <ActionIcon
                variant="subtle"
                color="red"
                mb={4}
                onClick={() => form.removeListItem('sizes', i)}
              >
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          ))}

          <Switch
            label="Available"
            mt="md"
            {...form.getInputProps('available', { type: 'checkbox' })}
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
