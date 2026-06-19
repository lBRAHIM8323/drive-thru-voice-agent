import { notifications } from '@mantine/notifications';

import { ApiError } from '../api/client';

export function notifySuccess(message: string, title = 'Success') {
  notifications.show({ title, message, color: 'green' });
}

export function notifyError(error: unknown, title = 'Something went wrong') {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : String(error);
  notifications.show({ title, message, color: 'red' });
}
