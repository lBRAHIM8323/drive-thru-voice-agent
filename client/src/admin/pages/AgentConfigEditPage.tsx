import { useEffect } from 'react';
import {
  Autocomplete,
  Button,
  ColorInput,
  Group,
  NumberInput,
  Select,
  Stack,
  Switch,
  TagsInput,
  Tabs,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useNavigate, useParams } from 'react-router-dom';

import {
  useAgentConfig,
  useAgentConfigs,
  useBranches,
  useCreateAgentConfig,
  useUpdateAgentConfig,
} from '../../api/hooks';
import type { AgentConfig } from '../../api/types';
import { AsyncState } from '../../components/AsyncState';
import { NumberOrNull } from '../../components/NumberOrNull';
import { PageHeader } from '../../components/PageHeader';
import { TriStateSelect } from '../../components/TriStateSelect';
import { defaultAgentConfig } from '../../lib/agentConfigDefaults';
import { notifyError, notifySuccess } from '../../lib/notify';
import {
  llmProviders,
  selectData,
  sttProviders,
  suggestedLLMModels,
  suggestedSTTModels,
  suggestedTTSModels,
  ttsProviders,
  turnModes,
  visualizers,
} from '../../lib/options';

interface FormValues {
  name: string;
  is_active: boolean;
  branch_id: string | null;
  config: AgentConfig;
}

export function AgentConfigEditPage() {
  const { id } = useParams();
  const isEdit = !!id;
  const navigate = useNavigate();

  const branches = useBranches();
  const configs = useAgentConfigs();
  const configQuery = useAgentConfig(id);
  const createMut = useCreateAgentConfig();
  const updateMut = useUpdateAgentConfig();

  const form = useForm<FormValues>({
    initialValues: {
      name: '',
      is_active: false,
      branch_id: null,
      config: defaultAgentConfig(),
    },
    validate: { name: (v) => (v.trim() ? null : 'Name is required') },
  });

  // Populate the form once the existing config + its summary are loaded.
  useEffect(() => {
    if (!isEdit || !configQuery.data) return;
    const summary = configs.data?.find((c) => c.id === id);
    form.setValues({
      name: summary?.name ?? '',
      is_active: summary?.is_active ?? false,
      branch_id: summary?.branch_id ?? null,
      config: configQuery.data,
    });
    form.resetDirty();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, id, configQuery.data, configs.data]);

  async function submit(values: FormValues) {
    try {
      if (isEdit) {
        await updateMut.mutateAsync({
          id: id!,
          body: { name: values.name, is_active: values.is_active, branch_id: values.branch_id, config: values.config },
        });
        notifySuccess('Config saved');
      } else {
        await createMut.mutateAsync({
          name: values.name,
          is_active: values.is_active,
          branch_id: values.branch_id,
          config: values.config,
        });
        notifySuccess('Config created');
      }
      navigate('/admin/agent-configs');
    } catch (e) {
      notifyError(e);
    }
  }

  const c = form.values.config;
  const branchData = (branches.data ?? []).map((b) => ({ value: b.id, label: b.name }));

  return (
    <>
      <PageHeader
        title={isEdit ? 'Edit agent config' : 'New agent config'}
        description="STT, LLM, TTS, prompt and behavior for a drive-thru session."
        actions={
          <Group>
            <Button variant="default" onClick={() => navigate('/admin/agent-configs')}>
              Back
            </Button>
            <Button
              onClick={() => form.onSubmit(submit)()}
              loading={createMut.isPending || updateMut.isPending}
            >
              {isEdit ? 'Save' : 'Create'}
            </Button>
          </Group>
        }
      />

      <AsyncState isLoading={isEdit && configQuery.isLoading} error={configQuery.error}>
        <form onSubmit={form.onSubmit(submit)}>
          <Tabs defaultValue="general">
            <Tabs.List mb="md">
              <Tabs.Tab value="general">General</Tabs.Tab>
              <Tabs.Tab value="stt">Speech-to-text</Tabs.Tab>
              <Tabs.Tab value="llm">LLM</Tabs.Tab>
              <Tabs.Tab value="tts">Text-to-speech</Tabs.Tab>
              <Tabs.Tab value="behavior">Behavior</Tabs.Tab>
              <Tabs.Tab value="appearance">Appearance</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="general">
              <Stack maw={720}>
                <Group grow>
                  <TextInput label="Name" withAsterisk {...form.getInputProps('name')} />
                  <Select
                    label="Branch"
                    placeholder="Global (all branches)"
                    clearable
                    data={branchData}
                    {...form.getInputProps('branch_id')}
                  />
                </Group>
                <Switch
                  label="Active"
                  {...form.getInputProps('is_active', { type: 'checkbox' })}
                />
                <Textarea
                  label="Instructions (system prompt)"
                  autosize
                  minRows={6}
                  {...form.getInputProps('config.instructions')}
                />
                <TextInput
                  label="Greeting"
                  description="Optional opening line spoken when a session starts."
                  value={c.greeting ?? ''}
                  onChange={(e) =>
                    form.setFieldValue('config.greeting', e.currentTarget.value || null)
                  }
                />
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="stt">
              <Stack maw={720}>
                <Group grow>
                  <Select
                    label="Provider"
                    allowDeselect={false}
                    data={selectData(sttProviders)}
                    {...form.getInputProps('config.stt.provider')}
                  />
                  <Autocomplete
                    label="Model"
                    data={suggestedSTTModels[c.stt.provider] ?? []}
                    {...form.getInputProps('config.stt.model')}
                  />
                  <TextInput label="Language" w={120} {...form.getInputProps('config.stt.language')} />
                </Group>
                <TagsInput
                  label="Keyterms"
                  description="Brand/keyword hints to bias transcription."
                  {...form.getInputProps('config.stt.keyterms')}
                />
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="llm">
              <Stack maw={720}>
                <Group grow>
                  <Select
                    label="Provider"
                    allowDeselect={false}
                    data={selectData(llmProviders)}
                    {...form.getInputProps('config.llm.provider')}
                  />
                  <Autocomplete
                    label="Model"
                    data={suggestedLLMModels[c.llm.provider] ?? []}
                    {...form.getInputProps('config.llm.model')}
                  />
                </Group>
                <Group grow>
                  <NumberOrNull
                    label="Temperature"
                    min={0}
                    max={2}
                    step={0.1}
                    value={c.llm.temperature}
                    onChange={(v) => form.setFieldValue('config.llm.temperature', v)}
                  />
                  <TriStateSelect
                    label="Parallel tool calls"
                    value={c.llm.parallel_tool_calls}
                    onChange={(v) => form.setFieldValue('config.llm.parallel_tool_calls', v)}
                  />
                </Group>
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="tts">
              <Stack maw={720}>
                <Group grow>
                  <Select
                    label="Provider"
                    allowDeselect={false}
                    data={selectData(ttsProviders)}
                    {...form.getInputProps('config.tts.provider')}
                  />
                  <Autocomplete
                    label="Model"
                    data={suggestedTTSModels[c.tts.provider] ?? []}
                    {...form.getInputProps('config.tts.model')}
                  />
                </Group>
                <Group grow>
                  <TextInput
                    label="Voice"
                    description="Voice id (Cartesia) or voice_id (ElevenLabs)."
                    value={c.tts.voice ?? ''}
                    onChange={(e) =>
                      form.setFieldValue('config.tts.voice', e.currentTarget.value || null)
                    }
                  />
                  <TextInput
                    label="Language"
                    value={c.tts.language ?? ''}
                    onChange={(e) =>
                      form.setFieldValue('config.tts.language', e.currentTarget.value || null)
                    }
                  />
                </Group>
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="behavior">
              <Stack maw={720}>
                <Select
                  label="Turn detection"
                  allowDeselect={false}
                  data={selectData(turnModes)}
                  w={240}
                  {...form.getInputProps('config.turn_detection.mode')}
                />

                <Switch
                  label="Voice activity detection (VAD)"
                  {...form.getInputProps('config.vad.enabled', { type: 'checkbox' })}
                />
                <Group grow>
                  <NumberOrNull
                    label="VAD activation threshold"
                    min={0}
                    max={1}
                    step={0.05}
                    value={c.vad.activation_threshold}
                    onChange={(v) => form.setFieldValue('config.vad.activation_threshold', v)}
                  />
                  <NumberOrNull
                    label="Min silence (s)"
                    min={0}
                    step={0.05}
                    value={c.vad.min_silence_duration}
                    onChange={(v) => form.setFieldValue('config.vad.min_silence_duration', v)}
                  />
                  <NumberOrNull
                    label="Min speech (s)"
                    min={0}
                    step={0.05}
                    value={c.vad.min_speech_duration}
                    onChange={(v) => form.setFieldValue('config.vad.min_speech_duration', v)}
                  />
                </Group>

                <Group grow>
                  <NumberInput
                    label="Max tool steps"
                    min={1}
                    {...form.getInputProps('config.session.max_tool_steps')}
                  />
                  <TriStateSelect
                    label="Allow interruptions"
                    value={c.session.allow_interruptions}
                    onChange={(v) => form.setFieldValue('config.session.allow_interruptions', v)}
                  />
                  <TriStateSelect
                    label="Preemptive generation"
                    value={c.session.preemptive_generation}
                    onChange={(v) => form.setFieldValue('config.session.preemptive_generation', v)}
                  />
                </Group>
                <Group grow>
                  <NumberOrNull
                    label="Min endpointing delay (s)"
                    min={0}
                    step={0.05}
                    value={c.session.min_endpointing_delay}
                    onChange={(v) => form.setFieldValue('config.session.min_endpointing_delay', v)}
                  />
                  <NumberOrNull
                    label="Max endpointing delay (s)"
                    min={0}
                    step={0.05}
                    value={c.session.max_endpointing_delay}
                    onChange={(v) => form.setFieldValue('config.session.max_endpointing_delay', v)}
                  />
                  <NumberOrNull
                    label="Min interruption duration (s)"
                    min={0}
                    step={0.05}
                    value={c.session.min_interruption_duration}
                    onChange={(v) => form.setFieldValue('config.session.min_interruption_duration', v)}
                  />
                </Group>

                <Switch
                  label="Background ambience"
                  {...form.getInputProps('config.background_audio.enabled', { type: 'checkbox' })}
                />
                <NumberInput
                  label="Background volume"
                  min={0}
                  max={2}
                  step={0.1}
                  w={240}
                  {...form.getInputProps('config.background_audio.volume')}
                />
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="appearance">
              <Stack maw={720}>
                <Select
                  label="Audio visualizer"
                  description="Which visualizer the customer sees on the order page."
                  allowDeselect={false}
                  data={selectData(visualizers)}
                  w={240}
                  {...form.getInputProps('config.ui.visualizer')}
                />
                <ColorInput
                  label="Accent color"
                  description="Optional. Tints the visualizer and accents."
                  value={c.ui.accent_color ?? ''}
                  onChange={(v) => form.setFieldValue('config.ui.accent_color', v || null)}
                />
                <TextInput
                  label="Customer heading"
                  description="Optional title shown to the customer."
                  value={c.ui.title ?? ''}
                  onChange={(e) =>
                    form.setFieldValue('config.ui.title', e.currentTarget.value || null)
                  }
                />
              </Stack>
            </Tabs.Panel>
          </Tabs>

          <Group justify="flex-end" mt="xl" maw={720}>
            <Button variant="default" onClick={() => navigate('/admin/agent-configs')}>
              Cancel
            </Button>
            <Button type="submit" loading={createMut.isPending || updateMut.isPending}>
              {isEdit ? 'Save' : 'Create'}
            </Button>
          </Group>
        </form>
      </AsyncState>
    </>
  );
}
