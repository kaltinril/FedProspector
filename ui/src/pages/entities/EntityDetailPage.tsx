import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { differenceInDays } from 'date-fns';
import { BackToSearch } from '@/components/shared/BackToSearch';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { DataTable } from '@/components/shared/DataTable';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { StatusChip } from '@/components/shared/StatusChip';
import { getEntity, getCompetitorProfile, getExclusionCheck } from '@/api/entities';
import { queryKeys } from '@/queries/queryKeys';
import { formatCurrency, formatNumber, formatPercent } from '@/utils/formatters';
import { formatDate, formatDateTime } from '@/utils/dateFormatters';
import type {
  EntityDetail,
  EntityAddressDto,
  EntityNaicsDto,
  EntityPocDto,
  CompetitorProfileDto,
  RecentAwardDto,
  ExclusionCheckDto,
  ExclusionDto,
} from '@/types/api';

// ---------------------------------------------------------------------------
// Business type code labels (SAM.gov reference)
// ---------------------------------------------------------------------------

const BUSINESS_TYPE_LABELS: Record<string, string> = {
  '2X': 'For-Profit Organization',
  '23': 'Minority Owned',
  '27': 'Self-Certified Small Disadvantaged Business',
  'A2': 'Woman Owned Business',
  'A5': 'Veteran Owned Business',
  'JT': 'Joint Venture Women Owned',
  'LJ': 'Limited Liability Corporation',
  'MF': 'Manufacturer of Goods',
  'OY': 'Black American Owned',
  'QF': 'Service-Disabled Veteran Owned',
  'XS': 'S Corporation',
  '8E': '8(a) Joint Venture',
  'GW': 'HUBZone Firm',
  'A8': 'SBA Certified 8(a)',
  '8A': 'SBA Certified 8(a) Joint Venture',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function findPhysicalAddress(addresses: EntityAddressDto[]): EntityAddressDto | undefined {
  return (
    addresses.find((a) => a.addressType.toLowerCase() === 'physical') ?? addresses[0]
  );
}

function formatAddress(addr: EntityAddressDto | undefined): string | null {
  if (!addr) return null;
  const parts = [
    addr.addressLine1,
    addr.addressLine2,
    [addr.city, addr.stateOrProvince].filter(Boolean).join(', '),
    addr.zipCode,
    addr.countryCode,
  ].filter(Boolean);
  return parts.join(', ');
}

function isExpiringWithin60Days(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return false;
  const days = differenceInDays(d, new Date());
  return days >= 0 && days <= 60;
}

// ---------------------------------------------------------------------------
// Tab 1 — Company Profile
// ---------------------------------------------------------------------------

function CompanyProfileTab({ entity }: { entity: EntityDetail }) {
  const physicalAddr = findPhysicalAddress(entity.addresses);
  const expiringSoon = isExpiringWithin60Days(entity.registrationExpirationDate);

  const facts = [
    { label: 'Legal Business Name', value: entity.legalBusinessName },
    { label: 'DBA Name', value: entity.dbaName },
    { label: 'UEI', value: entity.ueiSam },
    { label: 'CAGE Code', value: entity.cageCode },
    {
      label: 'Entity URL',
      value: entity.entityUrl ? (
        <Link href={entity.entityUrl} target="_blank" rel="noopener noreferrer">
          {entity.entityUrl}
        </Link>
      ) : null,
    },
    {
      label: 'Registration Status',
      value: entity.registrationStatus ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatusChip status={entity.registrationStatus} />
          {entity.registrationExpirationDate && (
            <Typography
              variant="body2"
              component="span"
              sx={{ color: expiringSoon ? 'warning.main' : 'text.secondary' }}
            >
              (expires {formatDate(entity.registrationExpirationDate)})
            </Typography>
          )}
        </Box>
      ) : null,
    },
    {
      label: 'Physical Address',
      value: formatAddress(physicalAddr),
    },
    {
      label: 'Congressional District',
      value: physicalAddr?.congressionalDistrict,
    },
  ];

  // --- NAICS columns ---
  const naicsColumns: GridColDef<EntityNaicsDto>[] = [
    { field: 'naicsCode', headerName: 'Code', width: 120 },
    {
      field: 'isPrimary',
      headerName: 'Primary',
      width: 100,
      renderCell: (params) =>
        params.value === 'Y' ? (
          <Chip label="Yes" size="small" color="primary" />
        ) : (
          <Chip label="No" size="small" variant="outlined" />
        ),
    },
    {
      field: 'sbaSmallBusiness',
      headerName: 'SBA Small Business',
      width: 160,
      renderCell: (params) =>
        params.value === 'Y' ? (
          <Chip label="Yes" size="small" color="success" />
        ) : (
          <Chip label="No" size="small" variant="outlined" />
        ),
    },
  ];

  // --- POC columns ---
  const pocColumns: GridColDef<EntityPocDto>[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 180,
      valueGetter: (_value: unknown, row: EntityPocDto) =>
        [row.firstName, row.middleInitial, row.lastName].filter(Boolean).join(' '),
    },
    { field: 'title', headerName: 'Title', flex: 1, minWidth: 150 },
    { field: 'pocType', headerName: 'Type', width: 140 },
    {
      field: 'location',
      headerName: 'Location',
      width: 180,
      valueGetter: (_value: unknown, row: EntityPocDto) =>
        [row.city, row.stateOrProvince, row.countryCode].filter(Boolean).join(', '),
    },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <KeyFactsGrid facts={facts} columns={2} />

      {/* Business Types */}
      {entity.businessTypes.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            Business Types
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {entity.businessTypes.map((bt) => (
              <Chip
                key={bt.businessTypeCode}
                label={BUSINESS_TYPE_LABELS[bt.businessTypeCode] ?? bt.businessTypeCode}
                size="small"
              />
            ))}
          </Box>
        </Box>
      )}

      {/* SBA Certifications */}
      {entity.sbaCertifications.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            SBA Certifications
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {entity.sbaCertifications.map((cert, idx) => (
              <Chip
                key={`${cert.sbaTypeCode}-${idx}`}
                label={[
                  cert.sbaTypeDesc ?? cert.sbaTypeCode,
                  cert.certificationEntryDate
                    ? `from ${formatDate(cert.certificationEntryDate)}`
                    : null,
                  cert.certificationExitDate
                    ? `to ${formatDate(cert.certificationExitDate)}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(' ')}
                size="small"
                color="info"
              />
            ))}
          </Box>
        </Box>
      )}

      {/* NAICS Codes */}
      {entity.naicsCodes.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            NAICS Codes
          </Typography>
          <DataTable
            columns={naicsColumns}
            rows={entity.naicsCodes.map((n, i) => ({ ...n, _idx: i }))}
            getRowId={(row) => `${(row as unknown as { _idx: number })._idx}-${row.naicsCode}`}
          />
        </Box>
      )}

      {/* PSC Codes */}
      {entity.pscCodes.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            PSC Codes
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {entity.pscCodes.map((psc) => (
              <Chip key={psc.pscCode} label={psc.pscCode} size="small" variant="outlined" />
            ))}
          </Box>
        </Box>
      )}

      {/* Points of Contact */}
      {entity.pointsOfContact.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            Points of Contact
          </Typography>
          <DataTable
            columns={pocColumns}
            rows={(entity.pointsOfContact ?? []).map((p, i) => ({ ...p, _idx: i }))}
            getRowId={(row) => (row as unknown as { _idx: number })._idx}
          />
        </Box>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab 2 — Competitor Analysis
// ---------------------------------------------------------------------------

function CompetitorAnalysisTab({ uei }: { uei: string }) {
  const navigate = useNavigate();

  const { data, isLoading, isError, refetch } = useQuery<CompetitorProfileDto>({
    queryKey: queryKeys.entities.competitor(uei),
    queryFn: () => getCompetitorProfile(uei),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) return <LoadingState message="Loading competitor profile..." />;
  if (isError)
    return (
      <ErrorState
        title="Failed to load competitor profile"
        message="Could not retrieve competitor analysis data."
        onRetry={() => refetch()}
      />
    );

  if (!data || data.pastContracts === 0) {
    return <EmptyState title="No contract history found" message="This entity has no recorded contract awards." />;
  }

  const summaryFacts = [
    { label: 'Total Contracts', value: formatNumber(data.pastContracts) },
    { label: 'Total Obligated', value: formatCurrency(data.totalObligated) },
    { label: 'Average Contract Size', value: formatCurrency(data.averageContractSize) },
    { label: 'Win Rate', value: formatPercent(data.winRate) },
    { label: 'Most Recent Award', value: formatDate(data.mostRecentAward) },
    { label: 'Primary NAICS', value: data.primaryNaics ? `${data.primaryNaics} — ${data.naicsDescription ?? ''}` : null },
    { label: 'NAICS Sector', value: data.naicsSector },
  ];

  const awardColumns: GridColDef<RecentAwardDto>[] = [
    {
      field: 'contractId',
      headerName: 'Contract ID',
      flex: 1,
      minWidth: 160,
      renderCell: (params) =>
        params.value ? (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/awards/${encodeURIComponent(params.value as string)}`);
            }}
          >
            {params.value}
          </Link>
        ) : (
          '--'
        ),
    },
    { field: 'vendorName', headerName: 'Vendor Name', flex: 1, minWidth: 180 },
    {
      field: 'dateSigned',
      headerName: 'Date Signed',
      width: 140,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    {
      field: 'dollarsObligated',
      headerName: 'Amount',
      width: 140,
      renderCell: (params) => <CurrencyDisplay value={params.value as number | null} />,
    },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <KeyFactsGrid facts={summaryFacts} columns={3} />

      {data.recentAwards.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            Recent Awards
          </Typography>
          <DataTable
            columns={awardColumns}
            rows={data.recentAwards}
            getRowId={(row: RecentAwardDto) =>
              row.contractId ?? `${row.vendorName}-${row.dateSigned}`
            }
          />
        </Box>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab 3 — Exclusion Check
// ---------------------------------------------------------------------------

function ExclusionCheckTab({ uei }: { uei: string }) {
  const { data, isLoading, isError, refetch } = useQuery<ExclusionCheckDto>({
    queryKey: queryKeys.entities.exclusions(uei),
    queryFn: () => getExclusionCheck(uei),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) return <LoadingState message="Checking exclusions..." />;
  if (isError)
    return (
      <ErrorState
        title="Failed to check exclusions"
        message="Could not retrieve exclusion data."
        onRetry={() => refetch()}
      />
    );
  if (!data) return null;

  const exclusionColumns: GridColDef<ExclusionDto>[] = [
    { field: 'exclusionType', headerName: 'Type', width: 140 },
    { field: 'exclusionProgram', headerName: 'Program', width: 160 },
    { field: 'excludingAgencyName', headerName: 'Agency', flex: 1, minWidth: 180 },
    {
      field: 'activationDate',
      headerName: 'Activation Date',
      width: 140,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    {
      field: 'terminationDate',
      headerName: 'Termination Date',
      width: 140,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    { field: 'additionalComments', headerName: 'Comments', flex: 1.5, minWidth: 200 },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {data.isExcluded ? (
        <Alert severity="error" variant="filled" sx={{ fontSize: '1.1rem' }}>
          EXCLUDED -- This entity has active exclusions
        </Alert>
      ) : (
        <Alert severity="success" variant="filled" sx={{ fontSize: '1.1rem' }}>
          CLEAR -- No active exclusions found
        </Alert>
      )}

      <Typography variant="body2" color="text.secondary">
        Last checked: {formatDateTime(data.checkedAt)}
      </Typography>

      {data.isExcluded && data.activeExclusions.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            Active Exclusions
          </Typography>
          <DataTable
            columns={exclusionColumns}
            rows={data.activeExclusions}
            getRowId={(row: ExclusionDto) =>
              `${row.exclusionType}-${row.excludingAgencyName}-${row.activationDate}`
            }
          />
        </Box>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab 4 — Federal Hierarchy
// ---------------------------------------------------------------------------

function FederalHierarchyTab() {
  return (
    <EmptyState
      title="Not applicable"
      message="Federal hierarchy display is not applicable for commercial entities. This tab will be enhanced when federal hierarchy data is needed."
    />
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

const TABS = [
  { value: 'profile', label: 'Company Profile' },
  { value: 'competitor', label: 'Competitor Analysis' },
  { value: 'exclusions', label: 'Exclusion Check' },
  { value: 'hierarchy', label: 'Federal Hierarchy' },
] as const;

type TabValue = (typeof TABS)[number]['value'];

export default function EntityDetailPage() {
  const { uei } = useParams<{ uei: string }>();
  const decodedUei = decodeURIComponent(uei ?? '');

  const [activeTab, setActiveTab] = useState<TabValue>('profile');

  const {
    data: entity,
    isLoading,
    isError,
    refetch,
  } = useQuery<EntityDetail>({
    queryKey: queryKeys.entities.detail(decodedUei),
    queryFn: () => getEntity(decodedUei),
    staleTime: 5 * 60 * 1000,
    enabled: decodedUei.length > 0,
  });

  if (isLoading) return <LoadingState message="Loading entity details..." />;
  if (isError) {
    return (
      <Box>
        <BackToSearch searchPath="/entities" />
        <ErrorState
          title="Failed to load entity"
          message="Could not retrieve entity details. The UEI may be invalid."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }
  if (!entity) return null;

  const isExcluded = entity.exclusionStatusFlag === 'Y';

  return (
    <Box>
      <BackToSearch searchPath="/entities" />

      <PageHeader
        title={entity.legalBusinessName}
        subtitle={`UEI: ${entity.ueiSam}${entity.dbaName && entity.dbaName !== entity.legalBusinessName ? ` | DBA: ${entity.dbaName}` : ''}`}
        actions={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            {entity.registrationStatus && (
              <StatusChip status={entity.registrationStatus} />
            )}
            <Chip
              label={isExcluded ? 'EXCLUDED' : 'Clear'}
              size="small"
              color={isExcluded ? 'error' : 'success'}
              variant="filled"
            />
            {entity.primaryNaics && (
              <Chip label={`NAICS: ${entity.primaryNaics}`} size="small" variant="outlined" />
            )}
            <Link
              href={`https://sam.gov/entity/${entity.ueiSam}/coreData`}
              target="_blank"
              rel="noopener noreferrer"
              variant="body2"
            >
              SAM.gov Profile
            </Link>
          </Box>
        }
      />

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={(_, value: TabValue) => setActiveTab(value)}
          variant="scrollable"
          scrollButtons="auto"
        >
          {TABS.map((tab) => (
            <Tab key={tab.value} label={tab.label} value={tab.value} />
          ))}
        </Tabs>
      </Box>

      <Box sx={{ pt: 3 }}>
        {activeTab === 'profile' && <CompanyProfileTab entity={entity} />}
        {activeTab === 'competitor' && <CompetitorAnalysisTab uei={decodedUei} />}
        {activeTab === 'exclusions' && <ExclusionCheckTab uei={decodedUei} />}
        {activeTab === 'hierarchy' && <FederalHierarchyTab />}
      </Box>
    </Box>
  );
}
