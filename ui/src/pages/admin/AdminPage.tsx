import { useState, lazy, Suspense } from 'react';
import Box from '@mui/material/Box';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';

const HealthTab = lazy(() => import('./HealthTab'));
const EtlStatusTab = lazy(() => import('./EtlStatusTab'));
const LoadHistoryTab = lazy(() => import('./LoadHistoryTab'));
const UserManagementTab = lazy(() => import('./UserManagementTab'));
const OrganizationsTab = lazy(() => import('./OrganizationsTab'));

const TAB_CONFIG = [
  { label: 'Health', subtitle: 'System health overview' },
  { label: 'ETL Status', subtitle: 'Data source status and API usage' },
  { label: 'Load History', subtitle: 'ETL load execution history' },
  { label: 'Users', subtitle: 'User account management' },
  { label: 'Organizations', subtitle: 'Organization management' },
] as const;

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Administration"
        subtitle={TAB_CONFIG[activeTab].subtitle}
      />

      <Tabs
        value={activeTab}
        onChange={(_e, newValue: number) => setActiveTab(newValue)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        {TAB_CONFIG.map((tab, idx) => (
          <Tab key={idx} label={tab.label} />
        ))}
      </Tabs>

      <Suspense fallback={<LoadingState />}>
        {activeTab === 0 && <HealthTab />}
        {activeTab === 1 && <EtlStatusTab />}
        {activeTab === 2 && <LoadHistoryTab />}
        {activeTab === 3 && <UserManagementTab />}
        {activeTab === 4 && <OrganizationsTab />}
      </Suspense>
    </Box>
  );
}
