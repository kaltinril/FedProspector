import { Link as RouterLink } from 'react-router-dom';
import Link from '@mui/material/Link';
import { useOrgLookup } from '@/queries/useHierarchy';

interface AgencyLinkProps {
  name: string | undefined | null;
  agencyCode?: string;
  fhOrgId?: number | null;
  level?: number;
}

export function AgencyLink({ name, agencyCode, fhOrgId: fhOrgIdProp }: AgencyLinkProps) {
  // Skip the lookup API call when fhOrgId is already provided by the caller.
  // The hook's enabled flag (!!lookupName) prevents it from firing when we pass undefined.
  const lookupName = fhOrgIdProp ? undefined : (name ?? undefined);
  const { fhOrgId: resolvedFhOrgId, isLoading } = useOrgLookup(lookupName, agencyCode);

  const fhOrgId = fhOrgIdProp ?? resolvedFhOrgId;

  if (!name) return null;

  if (!fhOrgIdProp && isLoading) {
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
