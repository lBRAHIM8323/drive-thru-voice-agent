import { Select } from '@mantine/core';

/** Select for an optional boolean: Default (null) / On (true) / Off (false). */
export function TriStateSelect({
  label,
  description,
  value,
  onChange,
}: {
  label: string;
  description?: string;
  value: boolean | null;
  onChange: (value: boolean | null) => void;
}) {
  const str = value === null ? 'default' : value ? 'true' : 'false';
  return (
    <Select
      label={label}
      description={description}
      allowDeselect={false}
      data={[
        { value: 'default', label: 'Default' },
        { value: 'true', label: 'On' },
        { value: 'false', label: 'Off' },
      ]}
      value={str}
      onChange={(v) => onChange(v === 'default' ? null : v === 'true')}
    />
  );
}
