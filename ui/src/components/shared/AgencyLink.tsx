import { Link as RouterLink } from 'react-router-dom';
import Link from '@mui/material/Link';
import { useOrgLookup } from '@/queries/useHierarchy';

interface AgencyLinkProps {
  name: string | undefined | null;
  agencyCode?: string;
  level?: number;
}

export function AgencyLink({ name, agencyCode }: AgencyLinkProps) {
  const { fhOrgId, isLoading } = useOrgLookup(name ?? undefined, agencyCode);

  if (!name) return null;

  if (isLoading) {
    return <>{name}</>;
  }

  if (fhOrgId) {
    return (
      <Link component={RouterLink} to={`/hierarchy/${fhOrgId}`} underline="hover">
        {name}
      </Link>
    );
  }

  return (
    <Link
      component={RouterLink}
      to={`/hierarchy?keyword=${encodeURIComponent(name)}`}
      underline="hover"
    >
      {name}
    </Link>
  );
}
