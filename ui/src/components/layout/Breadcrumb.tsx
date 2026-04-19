import { Link as RouterLink, useLocation } from 'react-router-dom';
import Breadcrumbs from '@mui/material/Breadcrumbs';
import Link from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import HomeOutlined from '@mui/icons-material/HomeOutlined';

const ROUTE_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  opportunities: 'Opportunities',
  awards: 'Awards',
  entities: 'Entities',
  prospects: 'Prospects',
  proposals: 'Proposals',
  'saved-searches': 'Saved Searches',
  organization: 'Organization',
  hierarchy: 'Federal Hierarchy',
  admin: 'Admin',
  setup: 'Company Setup',
  users: 'Users',
  profile: 'Profile',
};

function labelForSegment(segment: string): string {
  return ROUTE_LABELS[segment] ?? segment.charAt(0).toUpperCase() + segment.slice(1);
}

export function Breadcrumb() {
  const location = useLocation();
  const segments = location.pathname.split('/').filter(Boolean);

  // Don't render breadcrumbs on dashboard (it's home)
  if (segments.length === 0) return null;

  return (
    <Breadcrumbs aria-label="breadcrumb" sx={{ flexGrow: 1 }}>
      <Link
        component={RouterLink}
        to="/dashboard"
        underline="hover"
        color="inherit"
        sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
      >
        <HomeOutlined sx={{ fontSize: 18 }} />
        Home
      </Link>
      {segments.map((segment, index) => {
        const path = '/' + segments.slice(0, index + 1).join('/');
        const isLast = index === segments.length - 1;
        const label = labelForSegment(segment);

        if (isLast) {
          return (
            <Typography
              key={path}
              sx={{
                color: "text.primary",
                fontWeight: 500
              }}>
              {label}
            </Typography>
          );
        }

        return (
          <Link
            key={path}
            component={RouterLink}
            to={path}
            underline="hover"
            color="inherit"
          >
            {label}
          </Link>
        );
      })}
    </Breadcrumbs>
  );
}
