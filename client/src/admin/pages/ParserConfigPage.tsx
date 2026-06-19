import { useEffect } from 'react';
import {
  Autocomplete,
  Button,
  Card,
  Group,
  NumberInput,
  Select,
  Stack,
  Textarea,
} from '@mantine/core';
import { useForm } from '@mantine/form';

import { useParserConfig, useUpdateParserConfig } from '../../api/hooks';
import type { ParserProvider } from '../../api/types';
import { AsyncState } from '../../components/AsyncState';
import { PageHeader } from '../../components/PageHeader';
import { notifyError, notifySuccess } from '../../lib/notify';
import { parserProviders, selectData, suggestedLLMModels } from '../../lib/options';

interface FormValues {
  provider: ParserProvider;
  model: string;
  temperature: number | '';
  system_prompt: string;
}

export function ParserConfigPage() {
  const { data, isLoading, error } = useParserConfig();
  const updateMut = useUpdateParserConfig();

  const form = useForm<FormValues>({
    initialValues: { provider: 'anthropic', model: '', temperature: '', system_prompt: '' },
  });

  useEffect(() => {
    if (data) {
      form.setValues({
        provider: data.provider,
        model: data.model,
        temperature: data.temperature ?? '',
        system_prompt: data.system_prompt ?? '',
      });
      form.resetDirty();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  async function submit(values: FormValues) {
    try {
      await updateMut.mutateAsync({
        provider: values.provider,
        model: values.model.trim(),
        temperature: values.temperature === '' ? null : Number(values.temperature),
        system_prompt: values.system_prompt.trim() || null,
      });
      notifySuccess('Parser config saved');
    } catch (e) {
      notifyError(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Parser config"
        description="Which LLM parses uploaded menu documents into structured items."
      />
      <AsyncState isLoading={isLoading} error={error}>
        <Card withBorder radius="md" padding="lg" maw={680}>
          <form onSubmit={form.onSubmit(submit)}>
            <Stack>
              <Group grow>
                <Select
                  label="Provider"
                  data={selectData(parserProviders)}
                  allowDeselect={false}
                  {...form.getInputProps('provider')}
                />
                <Autocomplete
                  label="Model"
                  data={suggestedLLMModels[form.values.provider]}
                  {...form.getInputProps('model')}
                />
              </Group>
              <NumberInput
                label="Temperature"
                description="Optional. Leave blank to use the provider default."
                min={0}
                max={2}
                step={0.1}
                {...form.getInputProps('temperature')}
              />
              <Textarea
                label="System prompt override"
                description="Optional. Leave blank to use the built-in menu-extraction prompt."
                autosize
                minRows={3}
                {...form.getInputProps('system_prompt')}
              />
              <Group justify="flex-end">
                <Button type="submit" loading={updateMut.isPending}>
                  Save
                </Button>
              </Group>
            </Stack>
          </form>
        </Card>
      </AsyncState>
    </>
  );
}
