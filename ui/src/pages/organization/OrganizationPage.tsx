import { useState } from 'react';
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { PageHeader } from '@/components/shared/PageHeader';
import { OrgSettingsTab } from './OrgSettingsTab';
import { OrgMembersTab } from './OrgMembersTab';
import { OrgInvitesTab } from './OrgInvitesTab';
import { OrgActivityLogTab } from './OrgActivityLogTab';
import { OrgEntitiesTab } from './OrgEntitiesTab';

export default function OrganizationPage() {
  const [tab, setTab] = useState(0);

  return (
    <Box>
      <PageHeader
        title="Organization"
        subtitle="Manage your organization settings, members, and invitations"
      />

      <Tabs
        value={tab}
        onChange={(_e, newValue: number) => setTab(newValue)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}
      >
        <Tab label="Settings" />
        <Tab label="Entity Linking" />
        <Tab label="Members" />
        <Tab label="Invites" />
        <Tab label="Activity Log" />
      </Tabs>

      {tab === 0 && <ErrorBoundary><OrgSettingsTab /></ErrorBoundary>}
      {tab === 1 && <ErrorBoundary><OrgEntitiesTab /></ErrorBoundary>}
      {tab === 2 && <ErrorBoundary><OrgMembersTab /></ErrorBoundary>}
      {tab === 3 && <ErrorBoundary><OrgInvitesTab /></ErrorBoundary>}
      {tab === 4 && <ErrorBoundary><OrgActivityLogTab /></ErrorBoundary>}
    </Box>
  );
}
