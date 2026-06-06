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
  /** Controlled mode: external active tab value. */
  activeTab?: string;
  /** Controlled mode: called when the user clicks a tab. */
  onTabChange?: (tab: string) => void;
  /**
   * Top padding (MUI spacing units) between the tab strip and the active
   * content. Defaults to 3. Hubs set this to 0 because the reused page they
   * render already supplies its own top padding, so the default would stack.
   */
  contentTopPadding?: number;
}

export function TabbedDetailPage({
  children,
  tabs,
  defaultTab,
  activeTab: controlledTab,
  onTabChange,
  contentTopPadding = 3,
}: TabbedDetailPageProps) {
  const [internalTab, setInternalTab] = useState(
    defaultTab ?? tabs[0]?.value ?? '',
  );
  const activeTab = controlledTab ?? internalTab;
  const handleTabChange = onTabChange ?? setInternalTab;

  return (
    <Box>
      {children}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={(_, value: string) => handleTabChange(value)}
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
          <Box key={tab.value} sx={{ pt: contentTopPadding }}>
            {tab.content}
          </Box>
        ) : null,
      )}
    </Box>
  );
}
