import { NumberInput, type NumberInputProps } from '@mantine/core';

type Props = Omit<NumberInputProps, 'value' | 'onChange'> & {
  value: number | null;
  onChange: (value: number | null) => void;
};

/** NumberInput that maps an empty field to `null` (for optional numeric config). */
export function NumberOrNull({ value, onChange, ...rest }: Props) {
  return (
    <NumberInput
      value={value ?? ''}
      onChange={(v) => onChange(v === '' ? null : Number(v))}
      {...rest}
    />
  );
}
