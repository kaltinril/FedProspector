import { useEffect } from 'react';
import { useSnackbar } from 'notistack';
import { onApiError } from '@/utils/apiErrorHandler';
import type { ApiErrorEvent } from '@/utils/apiErrorHandler';

export function ApiErrorListener() {
  const { enqueueSnackbar } = useSnackbar();

  useEffect(() => {
    const unsubscribe = onApiError((event: ApiErrorEvent) => {
      switch (event.type) {
        case 'rate-limit':
          enqueueSnackbar(event.message, { variant: 'warning' });
          break;
        case 'conflict':
          enqueueSnackbar(event.message, { variant: 'warning' });
          break;
      }
    });
    return unsubscribe;
  }, [enqueueSnackbar]);

  return null;
}
