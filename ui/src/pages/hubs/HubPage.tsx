import { Suspense, useMemo } from 'react';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';

import { PageHeader } from '@/components/shared/PageHeader';
import { TabbedDetailPage } from '@/components/shared/TabbedDetailPage';
import { useSearchFilters } from '@/hooks/useSearchParams';
import type { Hub, HubTab } from '@/components/layout/hubConfig';

interface HubPageProps {
  hub: Hub;
}

/**
 * A "hub" is a thin tabbed shell that composes existing page components as tab
 * content. It does not own any data fetching of its own — each tab's queries
 * stay inside that tab's page component.
 *
 * The active tab is driven entirely by the `?tab=<slug>` query param so every
 * tab is deep-linkable. When the param is absent (or unknown) it falls back to
 * the hub's first tab. Tab clicks update the URL with `replace` (via
 * `useSearchFilters`), keeping the back button tied to real navigation rather
 * than every tab switch.
 *
 * Performance: `TabbedDetailPage` renders ONLY the active tab's content
 * (`tab.value === activeTab ? … : null`). Combined with each tab being a
 * `React.lazy` component, opening a hub never mounts — and therefore never
 * fires the queries of — non-active tabs. This is the key mitigation for the
 * slow Teaming / Market-Intel tabs, so no eager/hover prefetch is added.
 */
export function HubPage({ hub }: HubPageProps) {
  const firstSlug = hub.tabs[0]?.slug ?? '';
  const { filters, setFilters } = useSearchFilters({ tab: firstSlug });

  // Resolve the active tab from the URL, falling back to the first tab when the
  // slug is missing or does not match a known tab.
  const activeSlug = useMemo(() => {
    const fromUrl = filters.tab;
    return hub.tabs.some((t) => t.slug === fromUrl) ? fromUrl : firstSlug;
  }, [filters.tab, hub.tabs, firstSlug]);

  const tabs = useMemo(
    () =>
      hub.tabs.map((tab: HubTab) => {
        const Panel = tab.component;
        return {
          label: tab.label,
          value: tab.slug,
          content: (
            <Suspense fallback={<LinearProgress />}>
              <Panel />
            </Suspense>
          ),
        };
      }),
    [hub.tabs],
  );

  return (
    <Box>
      <PageHeader title={hub.label} subtitle={hub.subtitle} />
      <TabbedDetailPage
        tabs={tabs}
        activeTab={activeSlug}
        onTabChange={(slug) => setFilters({ tab: slug })}
      />
    </Box>
  );
}
