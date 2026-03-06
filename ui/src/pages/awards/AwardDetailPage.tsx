import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import { BackToSearch } from '@/components/shared/BackToSearch';
import { PageHeader } from '@/components/shared/PageHeader';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { BurnRateChart } from '@/components/shared/BurnRateChart';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { EmptyState } from '@/components/shared/EmptyState';
import { getAward, getBurnRate } from '@/api/awards';
import { queryKeys } from '@/queries/queryKeys';
import { formatDate } from '@/utils/dateFormatters';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import type { AwardDetail, TransactionDto, MonthlySpendDto } from '@/types/api';

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

const monthlySpendColumns: GridColDef<MonthlySpendDto>[] = [
  { field: 'yearMonth', headerName: 'Month', flex: 1, minWidth: 120 },
  {
    field: 'amount',
    headerName: 'Amount',
    flex: 1,
    minWidth: 140,
    align: 'right',
    headerAlign: 'right',
    valueFormatter: (value: number | null | undefined) => formatCurrency(value),
  },
  {
    field: 'transactionCount',
    headerName: 'Transaction Count',
    flex: 1,
    minWidth: 140,
    align: 'right',
    headerAlign: 'right',
  },
];

const transactionColumns: GridColDef<TransactionDto>[] = [
  {
    field: 'modificationNumber',
    headerName: 'Modification #',
    flex: 0.8,
    minWidth: 130,
    valueGetter: (_value: unknown, row: TransactionDto) =>
      row.modificationNumber ?? '--',
  },
  {
    field: 'actionType',
    headerName: 'Action Type',
    flex: 1,
    minWidth: 140,
    valueGetter: (_value: unknown, row: TransactionDto) =>
      row.actionTypeDescription ?? row.actionType ?? '--',
  },
  {
    field: 'federalActionObligation',
    headerName: 'Amount',
    flex: 1,
    minWidth: 140,
    align: 'right',
    headerAlign: 'right',
    valueFormatter: (value: number | null | undefined) => formatCurrency(value),
  },
  {
    field: 'actionDate',
    headerName: 'Date',
    flex: 0.8,
    minWidth: 120,
    valueFormatter: (value: string | null | undefined) =>
      value ? formatDate(value) : '--',
  },
];

// ---------------------------------------------------------------------------
// Helper: build place of performance string
// ---------------------------------------------------------------------------

function buildPlaceOfPerformance(award: AwardDetail): string | null {
  const parts: string[] = [];
  if (award.popState) parts.push(award.popState);
  if (award.popCountry && award.popCountry !== 'USA' && award.popCountry !== 'US')
    parts.push(award.popCountry);
  if (award.popZip) parts.push(award.popZip);
  return parts.length > 0 ? parts.join(', ') : null;
}

// ---------------------------------------------------------------------------
// Tab: Contract Details
// ---------------------------------------------------------------------------

function ContractDetailsTab({ award }: { award: AwardDetail }) {
  const navigate = useNavigate();

  const solicitationValue = award.solicitationNumber ? (
    <Link
      component="button"
      variant="body1"
      onClick={() =>
        navigate(
          `/opportunities/${encodeURIComponent(award.solicitationNumber!)}`,
        )
      }
    >
      {award.solicitationNumber}
    </Link>
  ) : null;

  const showBothCompletionDates =
    award.completionDate &&
    award.ultimateCompletionDate &&
    award.completionDate !== award.ultimateCompletionDate;

  const facts = [
    { label: 'Contract ID', value: award.contractId },
    { label: 'IDV PIID', value: award.idvPiid ?? null },
    { label: 'Solicitation Number', value: solicitationValue },
    { label: 'Solicitation Date', value: formatDate(award.solicitationDate) !== '--' ? formatDate(award.solicitationDate) : null },
    { label: 'Contract Type', value: award.typeOfContract },
    { label: 'Pricing Type', value: award.typeOfContractPricing },
    { label: 'NAICS Code', value: award.naicsCode },
    { label: 'PSC Code', value: award.pscCode },
    { label: 'Set-Aside Type', value: award.setAsideType },
    { label: 'Extent Competed', value: award.extentCompeted ?? 'N/A' },
    {
      label: 'Number of Offers',
      value: award.numberOfOffers != null ? formatNumber(award.numberOfOffers) : 'N/A',
    },
    { label: 'Description', value: award.description, fullWidth: true },
    {
      label: 'Place of Performance',
      value: buildPlaceOfPerformance(award),
    },
    { label: 'Completion Date', value: formatDate(award.completionDate) !== '--' ? formatDate(award.completionDate) : null },
    ...(showBothCompletionDates
      ? [
          {
            label: 'Ultimate Completion Date',
            value: formatDate(award.ultimateCompletionDate),
          },
        ]
      : []),
    { label: 'Contracting Office', value: award.contractingOfficeName },
    ...(award.fundingAgencyName && award.fundingAgencyName !== award.agencyName
      ? [{ label: 'Funding Agency', value: award.fundingAgencyName }]
      : []),
  ];

  return <KeyFactsGrid facts={facts} columns={2} />;
}

// ---------------------------------------------------------------------------
// Tab: Financials & Burn Rate
// ---------------------------------------------------------------------------

function FinancialsTab({
  award,
  contractId,
  enabled,
}: {
  award: AwardDetail;
  contractId: string;
  enabled: boolean;
}) {
  const {
    data: burnRate,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.awards.burnRate(contractId),
    queryFn: () => getBurnRate(contractId),
    staleTime: 5 * 60 * 1000,
    enabled,
  });

  if (isLoading) return <LoadingState message="Loading financial data..." />;
  if (isError)
    return (
      <ErrorState
        title="Failed to load burn rate"
        message="Could not retrieve financial data for this award."
        onRetry={() => refetch()}
      />
    );

  const monthlyData = (burnRate?.monthlyBreakdown ?? []).map((m) => ({
    month: m.yearMonth,
    amount: m.amount,
  }));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <BurnRateChart
        data={monthlyData}
        totalObligated={burnRate?.totalObligated ?? award.dollarsObligated ?? undefined}
        baseAndAllOptions={burnRate?.baseAndAllOptions ?? award.baseAndAllOptions ?? undefined}
      />

      {/* Monthly spend table */}
      <Box>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Monthly Spend
        </Typography>
        <DataTable
          columns={monthlySpendColumns}
          rows={burnRate?.monthlyBreakdown ?? []}
          getRowId={(row: MonthlySpendDto) => row.yearMonth}
        />
      </Box>

      {/* Transaction history table */}
      <Box>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Transaction History
        </Typography>
        <DataTable
          columns={transactionColumns}
          rows={award.transactions ?? []}
          getRowId={(_row: TransactionDto, index?: number) =>
            `${_row.actionDate}-${_row.modificationNumber ?? ''}-${index ?? 0}`
          }
        />
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: Vendor Profile
// ---------------------------------------------------------------------------

function VendorProfileTab({ award }: { award: AwardDetail }) {
  const navigate = useNavigate();
  const vendor = award.vendorProfile;

  if (!vendor) {
    return (
      <EmptyState
        title="Vendor not found"
        message="Vendor not found in entity database."
      />
    );
  }

  const facts = [
    { label: 'Legal Business Name', value: vendor.legalBusinessName },
    { label: 'DBA Name', value: vendor.dbaName },
    { label: 'UEI', value: vendor.ueiSam },
    { label: 'Registration Status', value: vendor.registrationStatus },
    { label: 'Primary NAICS', value: vendor.primaryNaics },
    {
      label: 'Entity URL',
      value: vendor.entityUrl ? (
        <Link href={vendor.entityUrl} target="_blank" rel="noopener noreferrer">
          {vendor.entityUrl}
        </Link>
      ) : null,
    },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Link
          component="button"
          variant="body1"
          onClick={() =>
            navigate(`/entities/${encodeURIComponent(vendor.ueiSam)}`)
          }
          sx={{ mb: 2, display: 'inline-block' }}
        >
          View full entity profile
        </Link>
      </Box>
      <KeyFactsGrid facts={facts} columns={2} />
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AwardDetailPage() {
  const { contractId } = useParams<{ contractId: string }>();
  const navigate = useNavigate();
  const decodedId = decodeURIComponent(contractId ?? '');

  const [activeTab, setActiveTab] = useState<string>('details');

  const {
    data: award,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.awards.detail(decodedId),
    queryFn: () => getAward(decodedId),
    staleTime: 5 * 60 * 1000,
    enabled: decodedId.length > 0,
  });

  const dateRangeText = useMemo(() => {
    if (!award) return null;
    const signed = formatDate(award.dateSigned);
    const completion = formatDate(award.completionDate);
    if (signed === '--' && completion === '--') return null;
    return `${signed} - ${completion}`;
  }, [award]);

  if (isLoading) return <LoadingState message="Loading award details..." />;
  if (isError || !award) {
    return (
      <Box>
        <BackToSearch searchPath="/awards" />
        <ErrorState
          title="Failed to load award"
          message="Could not retrieve award details. The contract may not exist or the server may be unavailable."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <BackToSearch searchPath="/awards" />

      <PageHeader
        title={`Contract: ${award.contractId}`}
        subtitle={award.solicitationNumber ?? undefined}
      />

      {/* Summary bar */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 3,
            alignItems: 'baseline',
          }}
        >
          {award.vendorName && (
            <Box>
              <Typography variant="body2" color="text.secondary">
                Vendor
              </Typography>
              <Link
                component="button"
                variant="body1"
                onClick={() => {
                  if (award.vendorUei) {
                    navigate(
                      `/entities/${encodeURIComponent(award.vendorUei)}`,
                    );
                  }
                }}
                sx={{
                  cursor: award.vendorUei ? 'pointer' : 'default',
                  textDecoration: award.vendorUei ? undefined : 'none',
                }}
              >
                {award.vendorName}
              </Link>
            </Box>
          )}
          {award.agencyName && (
            <Box>
              <Typography variant="body2" color="text.secondary">
                Agency
              </Typography>
              <Typography variant="body1">{award.agencyName}</Typography>
            </Box>
          )}
          <Box>
            <Typography variant="body2" color="text.secondary">
              Total Value
            </Typography>
            <Typography variant="body1">
              <CurrencyDisplay value={award.baseAndAllOptions} />
            </Typography>
          </Box>
          {dateRangeText && (
            <Box>
              <Typography variant="body2" color="text.secondary">
                Period
              </Typography>
              <Typography variant="body1">{dateRangeText}</Typography>
            </Box>
          )}
        </Box>
      </Paper>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={(_, value: string) => setActiveTab(value)}
          variant="scrollable"
          scrollButtons="auto"
        >
          <Tab label="Contract Details" value="details" />
          <Tab label="Financials & Burn Rate" value="financials" />
          <Tab label="Vendor Profile" value="vendor" />
        </Tabs>
      </Box>

      <Box sx={{ pt: 3 }}>
        {activeTab === 'details' && <ContractDetailsTab award={award} />}
        {activeTab === 'financials' && (
          <FinancialsTab
            award={award}
            contractId={decodedId}
            enabled={activeTab === 'financials'}
          />
        )}
        {activeTab === 'vendor' && <VendorProfileTab award={award} />}
      </Box>
    </Box>
  );
}
