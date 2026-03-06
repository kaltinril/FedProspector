import { useState } from 'react';
import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

interface TabConfig {
  label: string;
  value: string;
  content: React.ReactNode;
  disabled?: boolean;
}

interface TabbedDetailPageProps {
  children?: React.ReactNode;
  tabs: TabConfig[];
  defaultTab?: string;
}

export function TabbedDetailPage({
  children,
  tabs,
  defaultTab,
}: TabbedDetailPageProps) {
  const [activeTab, setActiveTab] = useState(
    defaultTab ?? tabs[0]?.value ?? '',
  );

  return (
    <Box>
      {children}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={(_, value: string) => setActiveTab(value)}
          variant="scrollable"
          scrollButtons="auto"
        >
          {tabs.map((tab) => (
            <Tab
              key={tab.value}
              label={tab.label}
              value={tab.value}
              disabled={tab.disabled}
            />
          ))}
        </Tabs>
      </Box>
      {tabs.map((tab) =>
        tab.value === activeTab ? (
          <Box key={tab.value} sx={{ pt: 3 }}>
            {tab.content}
          </Box>
        ) : null,
      )}
    </Box>
  );
}
