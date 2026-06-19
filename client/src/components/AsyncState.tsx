import { Alert, Center, Loader } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import type { ReactNode } from 'react';

export function AsyncState({
  isLoading,
  error,
  children,
}: {
  isLoading: boolean;
  error: unknown;
  children: ReactNode;
}) {
  if (isLoading) {
    return (
      <Center mih={200}>
        <Loader />
      </Center>
    );
  }
  if (error) {
    const message = error instanceof Error ? error.message : String(error);
    return (
      <Alert color="red" icon={<IconAlertTriangle size={18} />} title="Failed to load">
        {message}
      </Alert>
    );
  }
  return <>{children}</>;
}
