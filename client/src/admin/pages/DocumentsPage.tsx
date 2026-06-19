import { useEffect, useState } from 'react';
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import {
  IconCheck,
  IconEye,
  IconFileText,
  IconTrash,
  IconUpload,
  IconX,
} from '@tabler/icons-react';

import {
  useConfirmDocument,
  useDeleteDocument,
  useDocuments,
  useUpdateDocumentItems,
  useUploadDocument,
} from '../../api/hooks';
import type { ConfirmMode, DocumentRead, MenuItemCreate } from '../../api/types';
import { AsyncState } from '../../components/AsyncState';
import { PageHeader } from '../../components/PageHeader';
import { confirmDelete } from '../../components/confirmDelete';
import { notifyError, notifySuccess } from '../../lib/notify';

const STATUS_COLOR: Record<string, string> = {
  parsed: 'blue',
  confirmed: 'green',
  failed: 'red',
  parsing: 'yellow',
  uploaded: 'gray',
};

export function DocumentsPage() {
  const { data, isLoading, error } = useDocuments();
  const upload = useUploadDocument();
  const del = useDeleteDocument();

  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');
  const [reviewing, setReviewing] = useState<DocumentRead | null>(null);

  async function doUpload() {
    if (!file && !text.trim()) {
      notifyError('Provide a file or paste menu text');
      return;
    }
    try {
      const doc = await upload.mutateAsync({ file: file ?? undefined, text: text.trim() || undefined });
      notifySuccess(`Parsed ${doc.items.length} item(s)`);
      setFile(null);
      setText('');
      setReviewing(doc);
    } catch (e) {
      notifyError(e);
    }
  }

  async function remove(doc: DocumentRead) {
    if (!(await confirmDelete(`Delete document "${doc.filename ?? doc.id}"?`))) return;
    try {
      await del.mutateAsync(doc.id);
      notifySuccess('Document deleted');
    } catch (e) {
      notifyError(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Documents"
        description="Upload a menu (image, PDF, CSV, or text) and the configured LLM extracts items for review."
      />

      <Card withBorder radius="md" padding="lg" mb="lg">
        <Stack>
          <Dropzone
            onDrop={(files) => setFile(files[0] ?? null)}
            maxFiles={1}
            accept={['image/png', 'image/jpeg', 'image/webp', 'application/pdf', 'text/csv', 'text/plain', 'text/markdown']}
          >
            <Group justify="center" gap="lg" mih={100} style={{ pointerEvents: 'none' }}>
              <Dropzone.Accept>
                <IconUpload size={40} />
              </Dropzone.Accept>
              <Dropzone.Reject>
                <IconX size={40} />
              </Dropzone.Reject>
              <Dropzone.Idle>
                <IconFileText size={40} />
              </Dropzone.Idle>
              <div>
                <Text size="sm">
                  {file ? <b>{file.name}</b> : 'Drag a menu file here, or click to select'}
                </Text>
                <Text size="xs" c="dimmed">
                  Image, PDF, CSV, or text/markdown
                </Text>
              </div>
            </Group>
          </Dropzone>

          <Textarea
            label="…or paste menu text"
            placeholder="Espresso — $3.50&#10;Latte — S $4.00 / L $5.00"
            autosize
            minRows={2}
            value={text}
            onChange={(e) => setText(e.currentTarget.value)}
          />

          <Group justify="flex-end">
            <Button onClick={doUpload} loading={upload.isPending}>
              Parse
            </Button>
          </Group>
        </Stack>
      </Card>

      <AsyncState isLoading={isLoading} error={error}>
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Source</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Parser</Table.Th>
                <Table.Th>Items</Table.Th>
                <Table.Th>Created</Table.Th>
                <Table.Th w={100} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.map((doc) => (
                <Table.Tr key={doc.id}>
                  <Table.Td>{doc.filename ?? <Text c="dimmed">pasted text</Text>}</Table.Td>
                  <Table.Td>
                    <Badge color={STATUS_COLOR[doc.status] ?? 'gray'} variant="light">
                      {doc.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {doc.parser_provider}
                    {doc.parser_model ? ` / ${doc.parser_model}` : ''}
                  </Table.Td>
                  <Table.Td>{doc.items.length}</Table.Td>
                  <Table.Td>
                    {doc.created_at ? new Date(doc.created_at).toLocaleString() : '—'}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end">
                      <Tooltip label="Review & confirm">
                        <ActionIcon variant="subtle" onClick={() => setReviewing(doc)}>
                          <IconEye size={16} />
                        </ActionIcon>
                      </Tooltip>
                      <ActionIcon variant="subtle" color="red" onClick={() => remove(doc)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
              {data?.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={6} ta="center" c="dimmed">
                    No documents yet. Upload one above.
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </AsyncState>

      <ReviewModal doc={reviewing} onClose={() => setReviewing(null)} />
    </>
  );
}

function ReviewModal({ doc, onClose }: { doc: DocumentRead | null; onClose: () => void }) {
  const updateItems = useUpdateDocumentItems();
  const confirm = useConfirmDocument();
  const [items, setItems] = useState<MenuItemCreate[]>([]);
  const [mode, setMode] = useState<ConfirmMode>('merge');

  useEffect(() => {
    setItems(doc?.items ?? []);
  }, [doc]);

  if (!doc) return null;
  const readOnly = doc.status === 'confirmed';

  function patch(i: number, changes: Partial<MenuItemCreate>) {
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...changes } : it)));
  }

  async function save() {
    try {
      await updateItems.mutateAsync({ id: doc!.id, items });
      notifySuccess('Draft saved');
    } catch (e) {
      notifyError(e);
    }
  }

  async function doConfirm() {
    try {
      if (!readOnly) await updateItems.mutateAsync({ id: doc!.id, items });
      const committed = await confirm.mutateAsync({ id: doc!.id, mode });
      notifySuccess(`Committed ${committed.length} item(s) to the menu`);
      onClose();
    } catch (e) {
      notifyError(e);
    }
  }

  return (
    <Modal opened={!!doc} onClose={onClose} title="Review parsed menu" size="xl">
      {doc.error && (
        <Text c="red" mb="sm">
          {doc.error}
        </Text>
      )}
      <Table.ScrollContainer minWidth={600}>
        <Table verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Category</Table.Th>
              <Table.Th>Price</Table.Th>
              <Table.Th>Sizes</Table.Th>
              <Table.Th w={40} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((it, i) => (
              <Table.Tr key={i}>
                <Table.Td>
                  <TextInput
                    variant="unstyled"
                    value={it.name}
                    readOnly={readOnly}
                    onChange={(e) => patch(i, { name: e.currentTarget.value })}
                  />
                </Table.Td>
                <Table.Td>
                  <TextInput
                    variant="unstyled"
                    value={it.category}
                    readOnly={readOnly}
                    onChange={(e) => patch(i, { category: e.currentTarget.value })}
                  />
                </Table.Td>
                <Table.Td>
                  {it.sizes.length ? (
                    <Text size="sm" c="dimmed">
                      —
                    </Text>
                  ) : (
                    <NumberInput
                      variant="unstyled"
                      w={90}
                      hideControls
                      readOnly={readOnly}
                      value={it.price ?? ''}
                      onChange={(v) => patch(i, { price: v === '' ? null : Number(v) })}
                    />
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed">
                    {it.sizes.map((s) => `${s.size} ${s.price}`).join(' · ') || '—'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {!readOnly && (
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => setItems((prev) => prev.filter((_, idx) => idx !== i))}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      {readOnly ? (
        <Text mt="md" c="dimmed">
          This document was already confirmed.
        </Text>
      ) : (
        <Group justify="space-between" mt="lg">
          <Group gap="xs">
            <Text size="sm">Commit mode:</Text>
            <SegmentedControl
              size="xs"
              value={mode}
              onChange={(v) => setMode(v as ConfirmMode)}
              data={[
                { label: 'Merge', value: 'merge' },
                { label: 'Replace all', value: 'replace' },
              ]}
            />
          </Group>
          <Group>
            <Button variant="default" onClick={save} loading={updateItems.isPending}>
              Save draft
            </Button>
            <Button
              leftSection={<IconCheck size={16} />}
              onClick={doConfirm}
              loading={confirm.isPending}
            >
              Confirm to menu
            </Button>
          </Group>
        </Group>
      )}
    </Modal>
  );
}
