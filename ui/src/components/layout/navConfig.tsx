import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import EmojiEventsOutlined from '@mui/icons-material/EmojiEventsOutlined';
import BusinessOutlined from '@mui/icons-material/BusinessOutlined';
import TrackChangesOutlined from '@mui/icons-material/TrackChangesOutlined';
import BookmarkBorderOutlined from '@mui/icons-material/BookmarkBorderOutlined';
import CorporateFareOutlined from '@mui/icons-material/CorporateFareOutlined';
import AdminPanelSettingsOutlined from '@mui/icons-material/AdminPanelSettingsOutlined';
import RecommendOutlined from '@mui/icons-material/RecommendOutlined';
import HealthAndSafetyOutlined from '@mui/icons-material/HealthAndSafetyOutlined';
import AccountCircleOutlined from '@mui/icons-material/AccountCircleOutlined';

import { HUBS } from '@/components/layout/hubConfig';

export interface NavItem {
  label: string;
  icon: React.ReactElement;
  route: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

/**
 * Tier 1 — Destinations. Flat sidebar items with their own routes (no tabs).
 * These are the places a user starts from.
 */
export const DESTINATIONS: NavItem[] = [
  { label: 'Dashboard', icon: <DashboardOutlined />, route: '/dashboard' },
  { label: 'Recommended', icon: <RecommendOutlined />, route: '/opportunities/recommended' },
  { label: 'Prospects', icon: <TrackChangesOutlined />, route: '/prospects' },
  { label: 'Opportunities', icon: <SearchOutlined />, route: '/opportunities' },
  { label: 'Awards', icon: <EmojiEventsOutlined />, route: '/awards' },
  { label: 'Entities', icon: <BusinessOutlined />, route: '/entities' },
];

/**
 * Tier 2 — Hubs. Derived from the single hub config so the sidebar, command
 * palette and router never drift. Each hub links to its landing route; the hub
 * page itself renders the tabs.
 */
export const HUB_NAV_ITEMS: NavItem[] = HUBS.map((hub) => ({
  label: hub.label,
  icon: hub.icon,
  route: hub.route,
}));

/**
 * Tier 3 — Account. Rendered in the top-bar avatar menu (NOT the sidebar).
 * `adminOnly` items are gated on the system-admin role exactly as before.
 */
export interface AccountItem extends NavItem {
  adminOnly?: boolean;
}

export const ACCOUNT_ITEMS: AccountItem[] = [
  { label: 'Profile', icon: <AccountCircleOutlined />, route: '/profile' },
  { label: 'Organization', icon: <CorporateFareOutlined />, route: '/organization' },
  { label: 'Saved Searches', icon: <BookmarkBorderOutlined />, route: '/saved-searches' },
  { label: 'Data Quality', icon: <HealthAndSafetyOutlined />, route: '/insights/data-quality', adminOnly: true },
  { label: 'Admin', icon: <AdminPanelSettingsOutlined />, route: '/admin', adminOnly: true },
];

export const ADMIN_ITEM: AccountItem = ACCOUNT_ITEMS.find((i) => i.route === '/admin')!;

/**
 * Returns the account items visible to the current user, dropping admin-only
 * entries (Data Quality, Admin) for non-system-admins.
 */
export function getAccountItems(isSystemAdmin: boolean): AccountItem[] {
  return ACCOUNT_ITEMS.filter((item) => !item.adminOnly || isSystemAdmin);
}

/**
 * Sidebar sections for the 3-tier IA: Tier-1 destinations (flat, no header) and
 * the Tier-2 "HUBS" group. Tier-3 account links live in the top bar, not here.
 *
 * The shape (NavSection[]) is preserved so the command palette can flatten it,
 * but the palette also needs the account links, so it should combine this with
 * `getAccountItems`. The Sidebar renders Destinations flat and Hubs under a
 * header — see Sidebar.tsx.
 */
export function getNavSections(_isSystemAdmin: boolean): NavSection[] {
  void _isSystemAdmin;
  return [
    { title: 'Destinations', items: [...DESTINATIONS] },
    { title: 'Hubs', items: [...HUB_NAV_ITEMS] },
  ];
}
