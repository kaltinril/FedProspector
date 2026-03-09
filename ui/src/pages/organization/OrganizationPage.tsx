import { useState } from 'react';
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

import { PageHeader } from '@/components/shared/PageHeader';
import { OrgSettingsTab } from './OrgSettingsTab';
import { OrgMembersTab } from './OrgMembersTab';
import { OrgInvitesTab } from './OrgInvitesTab';
import { OrgActivityLogTab } from './OrgActivityLogTab';

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
        <Tab label="Members" />
        <Tab label="Invites" />
        <Tab label="Activity Log" />
      </Tabs>

      {tab === 0 && <OrgSettingsTab />}
      {tab === 1 && <OrgMembersTab />}
      {tab === 2 && <OrgInvitesTab />}
      {tab === 3 && <OrgActivityLogTab />}
    </Box>
  );
}
