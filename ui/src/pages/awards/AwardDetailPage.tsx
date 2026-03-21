import { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
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
import { getAward, getBurnRate, searchAwards, requestAwardLoad, getAwardLoadStatus } from '@/api/awards';
import { getSubawardsByPrime } from '@/api/subawards';
import { queryKeys } from '@/queries/queryKeys';
import { formatDate } from '@/utils/dateFormatters';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import { buildPlaceOfPerformance } from '@/utils/format';
import type { AwardDetail, AwardSearchResult, TransactionDto, MonthlySpendDto, SubawardDetailDto } from '@/types/api';

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
// Tab: Contract Details
// ---------------------------------------------------------------------------

function ContractDetailsTab({ award }: { award: AwardDetail }) {
  const solicitationValue = award.solicitationNumber ?? null;

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
      <EmptyState
        title="No financial data available"
        message="This contract does not have USASpending transaction data linked yet."
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
          rows={(award.transactions ?? []).map((t, i) => ({ ...t, _idx: i }))}
          getRowId={(row) =>
            `${(row as unknown as { _idx: number })._idx}-${row.actionDate}`
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

  const {
    data: otherAwardsData,
    isLoading: otherAwardsLoading,
    isError: otherAwardsError,
    refetch: otherAwardsRefetch,
  } = useQuery({
    queryKey: queryKeys.awards.list({ vendorUei: award.vendorUei, pageSize: 10, sortBy: 'dateSigned', sortDescending: true }),
    queryFn: () => searchAwards({ vendorUei: award.vendorUei!, pageSize: 10, sortBy: 'dateSigned', sortDescending: true }),
    staleTime: 5 * 60 * 1000,
    enabled: !!award.vendorUei,
  });

  const otherAwards = useMemo(() => {
    if (!otherAwardsData?.items) return [];
    return otherAwardsData.items.filter((a) => a.contractId !== award.contractId);
  }, [otherAwardsData, award.contractId]);

  const otherAwardsColumns: GridColDef<AwardSearchResult>[] = useMemo(() => [
    {
      field: 'contractId',
      headerName: 'Contract ID',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => (
        <Link
          component="button"
          variant="body2"
          onClick={() => navigate(`/awards/${encodeURIComponent(params.value)}`)}
        >
          {params.value}
        </Link>
      ),
    },
    {
      field: 'dateSigned',
      headerName: 'Date Signed',
      flex: 0.8,
      minWidth: 120,
      valueFormatter: (value: string | null | undefined) =>
        value ? formatDate(value) : '--',
    },
    {
      field: 'dollarsObligated',
      headerName: 'Obligated',
      flex: 1,
      minWidth: 140,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value),
    },
    {
      field: 'baseAndAllOptions',
      headerName: 'Ceiling',
      flex: 1,
      minWidth: 140,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value),
    },
    {
      field: 'naicsCode',
      headerName: 'NAICS',
      flex: 0.6,
      minWidth: 90,
    },
  ], [navigate]);

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

      {/* Other Awards by Same Vendor */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Other Awards by This Vendor
        </Typography>
        {otherAwardsLoading && <LoadingState message="Loading other awards..." />}
        {otherAwardsError && (
          <ErrorState
            title="Failed to load other awards"
            message="Could not retrieve other awards for this vendor."
            onRetry={() => otherAwardsRefetch()}
          />
        )}
        {!otherAwardsLoading && !otherAwardsError && otherAwards.length === 0 && (
          <EmptyState
            title="No other awards"
            message="No other awards found for this vendor."
          />
        )}
        {!otherAwardsLoading && !otherAwardsError && otherAwards.length > 0 && (
          <DataTable
            columns={otherAwardsColumns}
            rows={otherAwards}
            getRowId={(row: AwardSearchResult) => row.contractId}
          />
        )}
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: Subcontractors
// ---------------------------------------------------------------------------

function SubcontractorsTab({
  contractId,
  enabled,
}: {
  contractId: string;
  enabled: boolean;
}) {
  const navigate = useNavigate();

  const subcontractorColumns: GridColDef<SubawardDetailDto & { _idx: number }>[] = useMemo(() => [
    {
      field: 'subName',
      headerName: 'Sub Name',
      flex: 1.5,
      minWidth: 180,
      valueGetter: (_value: unknown, row: SubawardDetailDto) =>
        row.subName ?? '--',
    },
    {
      field: 'subUei',
      headerName: 'UEI',
      flex: 0.8,
      minWidth: 130,
      renderCell: (params) => {
        const uei = params.value as string | null | undefined;
        if (!uei) return '--';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={() => navigate(`/entities/${encodeURIComponent(uei)}`)}
          >
            {uei}
          </Link>
        );
      },
    },
    {
      field: 'subAmount',
      headerName: 'Amount',
      flex: 1,
      minWidth: 140,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value),
    },
    {
      field: 'subDate',
      headerName: 'Date',
      flex: 0.8,
      minWidth: 120,
      valueFormatter: (value: string | null | undefined) =>
        value ? formatDate(value) : '--',
    },
    {
      field: 'subDescription',
      headerName: 'Description',
      flex: 2,
      minWidth: 200,
      valueGetter: (_value: unknown, row: SubawardDetailDto) =>
        row.subDescription ?? '--',
    },
    {
      field: 'naicsCode',
      headerName: 'NAICS',
      flex: 0.6,
      minWidth: 90,
      valueGetter: (_value: unknown, row: SubawardDetailDto) =>
        row.naicsCode ?? '--',
    },
  ], [navigate]);

  const {
    data: subawards,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.subawards.byPrime(contractId),
    queryFn: () => getSubawardsByPrime(contractId),
    staleTime: 5 * 60 * 1000,
    enabled,
  });

  if (isLoading) return <LoadingState message="Loading subcontractor data..." />;
  if (isError)
    return (
      <ErrorState
        title="Failed to load subcontractors"
        message="Could not retrieve subaward data for this contract."
        onRetry={() => refetch()}
      />
    );

  if (!subawards || subawards.length === 0) {
    return (
      <EmptyState
        title="No subcontractors"
        message="No subaward data reported for this contract."
      />
    );
  }

  const rows = subawards.map((s, i) => ({ ...s, _idx: i }));

  return (
    <DataTable
      columns={subcontractorColumns}
      rows={rows}
      getRowId={(row: SubawardDetailDto & { _idx: number }) =>
        `${row._idx}-${row.subUei ?? 'unknown'}`
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AwardDetailPage() {
  const { contractId } = useParams<{ contractId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const decodedId = decodeURIComponent(contractId ?? '');

  const [activeTab, setActiveTab] = useState<string>('details');
  const [loadRequested, setLoadRequested] = useState(false);

  const {
    data: response,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.awards.detail(decodedId),
    queryFn: () => getAward(decodedId),
    staleTime: 5 * 60 * 1000,
    enabled: decodedId.length > 0,
  });

  const award = response?.detail ?? null;
  const dataStatus = response?.dataStatus ?? 'not_loaded';

  // Poll load status while loading is in progress
  const { data: loadStatus } = useQuery({
    queryKey: queryKeys.awards.loadStatus(decodedId),
    queryFn: () => getAwardLoadStatus(decodedId),
    enabled: loadRequested || response?.loadStatus?.status === 'PENDING' || response?.loadStatus?.status === 'PROCESSING',
    refetchInterval: 4000,
  });

  // When load completes, refresh the award detail and stop polling
  useEffect(() => {
    if (loadStatus?.status === 'COMPLETED') {
      setLoadRequested(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.awards.detail(decodedId) });
    }
  }, [loadStatus?.status, decodedId, queryClient]);

  const handleLoadRequest = async () => {
    try {
      await requestAwardLoad(decodedId, 'usaspending');
      setLoadRequested(true);
    } catch {
      // Error handled by UI
    }
  };

  const dateRangeText = useMemo(() => {
    if (!award) return null;
    const signed = formatDate(award.dateSigned);
    const completion = formatDate(award.completionDate);
    if (signed === '--' && completion === '--') return null;
    return `${signed} - ${completion}`;
  }, [award]);

  if (isLoading) return <LoadingState message="Loading award details..." />;

  if (isError) {
    return (
      <Box>
        <BackToSearch searchPath="/awards" />
        <ErrorState
          title="Failed to load award"
          message="Could not connect to the server. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  if (dataStatus === 'not_loaded') {
    const isLoadingData = loadRequested || response?.loadStatus?.status === 'PENDING' || response?.loadStatus?.status === 'PROCESSING';
    return (
      <Box>
        <BackToSearch searchPath="/awards" />
        <PageHeader title={`Contract: ${decodedId}`} />
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" gutterBottom>
            Award Not Yet Loaded
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            This contract has not been loaded into FedProspect yet.
            Click below to fetch the data from USASpending.gov.
          </Typography>
          {isLoadingData ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
              <CircularProgress size={32} />
              <Typography variant="body2" color="text.secondary">
                Loading data from USASpending.gov...
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button variant="contained" onClick={handleLoadRequest}>
                Load This Award
              </Button>
              <Button
                variant="outlined"
                href={`https://www.usaspending.gov/search/?hash=&filters=%7B%22keyword%22%3A%22${encodeURIComponent(decodedId)}%22%7D`}
                target="_blank"
                rel="noopener noreferrer"
              >
                View on USASpending.gov
              </Button>
            </Box>
          )}
          {loadStatus?.status === 'FAILED' && (
            <Typography color="error" sx={{ mt: 2 }}>
              Load failed: {loadStatus.errorMessage ?? 'Unknown error'}
            </Typography>
          )}
        </Paper>
      </Box>
    );
  }

  if (!award) {
    return (
      <Box>
        <BackToSearch searchPath="/awards" />
        <ErrorState
          title="No data available"
          message="Award data is not available."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  const showPartialBanner = dataStatus === 'partial';

  return (
    <Box>
      <BackToSearch searchPath="/awards" />

      <PageHeader
        title={`Contract: ${award.contractId}`}
        subtitle={award.solicitationNumber ?? undefined}
      />

      {showPartialBanner && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Partial data available from USASpending.gov. Full contract details from FPDS are loading in the background.
        </Alert>
      )}

      {/* Summary bar */}
      <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 }, mb: { xs: 2, md: 3 } }}>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: { xs: 2, md: 3 },
            alignItems: 'baseline',
          }}
        >
          <Box>
            <Typography variant="body2" color="text.secondary">
              Vendor
            </Typography>
            {award.vendorUei ? (
              <Link
                component="button"
                variant="body1"
                onClick={() =>
                  navigate(
                    `/entities/${encodeURIComponent(award.vendorUei!)}`,
                  )
                }
              >
                {award.vendorName}
              </Link>
            ) : (
              <Typography variant="body1">
                {award.vendorName ?? 'Unknown Vendor'}
              </Typography>
            )}
          </Box>
          {award.idvPiid && (
            <Box>
              <Typography variant="body2" color="text.secondary">
                Parent Contract
              </Typography>
              <Typography variant="body1">{award.idvPiid}</Typography>
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
          {award.fundingAgencyName && award.fundingAgencyName !== award.agencyName && (
            <Box>
              <Typography variant="body2" color="text.secondary">
                Funding Agency
              </Typography>
              <Typography variant="body1">{award.fundingAgencyName}</Typography>
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
          <Tab label="Subcontractors" value="subcontractors" />
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
        {activeTab === 'subcontractors' && (
          <SubcontractorsTab
            contractId={decodedId}
            enabled={activeTab === 'subcontractors'}
          />
        )}
      </Box>
    </Box>
  );
}
