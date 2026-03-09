import { useState, useMemo, lazy, Suspense } from 'react';
import Box from '@mui/material/Box';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { useAuth } from '@/auth/useAuth';

const HealthTab = lazy(() => import('./HealthTab'));
const EtlStatusTab = lazy(() => import('./EtlStatusTab'));
const LoadHistoryTab = lazy(() => import('./LoadHistoryTab'));
const UserManagementTab = lazy(() => import('./UserManagementTab'));
const OrganizationsTab = lazy(() => import('./OrganizationsTab'));

interface TabDef {
  label: string;
  subtitle: string;
  component: React.LazyExoticComponent<() => React.JSX.Element>;
}

const BASE_TABS: TabDef[] = [
  { label: 'Health', subtitle: 'System health overview', component: HealthTab },
  { label: 'Users', subtitle: 'User account management', component: UserManagementTab },
];

const ETL_STATUS_TAB: TabDef = {
  label: 'ETL Status',
  subtitle: 'Data source status and API usage',
  component: EtlStatusTab,
};

const LOAD_HISTORY_TAB: TabDef = {
  label: 'Load History',
  subtitle: 'ETL load execution history',
  component: LoadHistoryTab,
};

const ORGS_TAB: TabDef = {
  label: 'Organizations',
  subtitle: 'Organization management',
  component: OrganizationsTab,
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState(0);
  const { isSystemAdmin } = useAuth();

  const tabs = useMemo(
    () =>
      isSystemAdmin
        ? [...BASE_TABS, ETL_STATUS_TAB, LOAD_HISTORY_TAB, ORGS_TAB]
        : BASE_TABS,
    [isSystemAdmin],
  );

  const ActiveComponent = tabs[activeTab]?.component;

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Administration"
        subtitle={tabs[activeTab]?.subtitle ?? ''}
      />

      <Tabs
        value={activeTab}
        onChange={(_e, newValue: number) => setActiveTab(newValue)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        {tabs.map((tab, idx) => (
          <Tab key={idx} label={tab.label} />
        ))}
      </Tabs>

      <Suspense fallback={<LoadingState />}>
        {ActiveComponent && <ActiveComponent />}
      </Suspense>
    </Box>
  );
}
