import { modals } from '@mantine/modals';

/** Promise-based confirm dialog; resolves true when the user confirms. */
export function confirmDelete(message: string, title = 'Please confirm'): Promise<boolean> {
  return new Promise((resolve) => {
    modals.openConfirmModal({
      title,
      children: message,
      labels: { confirm: 'Delete', cancel: 'Cancel' },
      confirmProps: { color: 'red' },
      onConfirm: () => resolve(true),
      onCancel: () => resolve(false),
      onClose: () => resolve(false),
    });
  });
}
