import { useState } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SearchIcon from '@mui/icons-material/Search';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import {
  useNaicsSectors,
  useNaicsChildren,
  useNaicsDetail,
  useNaicsSearch,
} from '@/queries/useOrganization';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import type { NaicsHierarchyNode, NaicsDetailDto } from '@/types/organization';

/**
 * Phase 129 Unit E — NAICS hierarchy browser.
 *
 * Expandable tree of the NAICS taxonomy. Sectors load up front; each node's
 * children are fetched lazily the first time it is expanded. Leaf (6-digit)
 * nodes show their SBA size standard and expose a "view detail" affordance.
 * A search box filters by code or keyword (reuses the reference NAICS search).
 */
export default function NaicsBrowserPage() {
  const [search, setSearch] = useState('');
  const [detailCode, setDetailCode] = useState<string | null>(null);

  const trimmed = search.trim();
  const isSearching = trimmed.length >= 2;

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="NAICS Browser"
        subtitle="Explore the NAICS classification hierarchy and SBA small-business size standards"
      />

      <TextField
        fullWidth
        size="small"
        placeholder="Search by NAICS code or keyword (min 2 characters)"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 3, maxWidth: 560 }}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          },
        }}
      />

      {isSearching ? (
        <SearchResults query={trimmed} onViewDetail={setDetailCode} />
      ) : (
        <HierarchyTree onViewDetail={setDetailCode} />
      )}

      <NaicsDetailDialog
        code={detailCode}
        onClose={() => setDetailCode(null)}
      />
    </Box>
  );
}

// --- Hierarchy tree ---

function HierarchyTree({ onViewDetail }: { onViewDetail: (code: string) => void }) {
  const { data: sectors, isLoading, isError, refetch } = useNaicsSectors();

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (!sectors || sectors.length === 0) {
    return (
      <EmptyState
        title="No NAICS Data"
        message="The NAICS reference table has no active sectors loaded."
      />
    );
  }

  return (
    <Paper variant="outlined">
      <List disablePadding>
        {sectors.map((node) => (
          <NaicsTreeNode
            key={node.code}
            node={node}
            depth={0}
            onViewDetail={onViewDetail}
          />
        ))}
      </List>
    </Paper>
  );
}

function NaicsTreeNode({
  node,
  depth,
  onViewDetail,
}: {
  node: NaicsHierarchyNode;
  depth: number;
  onViewDetail: (code: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  // Lazy: only fetch children once the node has been expanded at least once.
  const { data: children, isLoading, isError, refetch } = useNaicsChildren(
    node.code,
    expanded && !node.isLeaf,
  );

  const toggle = () => {
    if (!node.isLeaf) setExpanded((prev) => !prev);
  };

  return (
    <>
      <ListItem
        disablePadding
        secondaryAction={
          node.isLeaf ? (
            <Tooltip title="View size standard detail">
              <IconButton
                edge="end"
                size="small"
                aria-label={`View detail for ${node.code}`}
                onClick={() => onViewDetail(node.code)}
              >
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          ) : undefined
        }
      >
        <ListItemButton
          onClick={toggle}
          sx={{ pl: 2 + depth * 2.5, py: 0.75 }}
        >
          <Box sx={{ width: 28, display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            {node.isLeaf ? null : expanded ? (
              <ExpandMoreIcon fontSize="small" color="action" />
            ) : (
              <ChevronRightIcon fontSize="small" color="action" />
            )}
          </Box>
          <Chip
            label={node.code}
            size="small"
            variant="outlined"
            sx={{ mr: 1.5, fontFamily: 'monospace', flexShrink: 0 }}
          />
          <ListItemText
            primary={node.title}
            slotProps={{
              primary: { sx: { fontSize: '0.875rem' } },
            }}
          />
          {node.levelName && (
            <Typography
              variant="caption"
              sx={{ color: 'text.secondary', ml: 1, flexShrink: 0 }}
            >
              {node.levelName}
            </Typography>
          )}
        </ListItemButton>
      </ListItem>

      {!node.isLeaf && (
        <Collapse in={expanded} timeout="auto" unmountOnExit>
          {isLoading ? (
            <Box sx={{ pl: 4 + depth * 2.5, py: 1 }}>
              <CircularProgress size={18} />
            </Box>
          ) : isError ? (
            <Box sx={{ pl: 4 + depth * 2.5, py: 1 }}>
              <Typography variant="caption" color="error">
                Failed to load children.{' '}
                <Button size="small" onClick={() => refetch()}>
                  Retry
                </Button>
              </Typography>
            </Box>
          ) : children && children.length > 0 ? (
            <List disablePadding>
              {children.map((child) => (
                <NaicsTreeNode
                  key={child.code}
                  node={child}
                  depth={depth + 1}
                  onViewDetail={onViewDetail}
                />
              ))}
            </List>
          ) : (
            <Box sx={{ pl: 4 + depth * 2.5, py: 1 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                No further subdivisions.
              </Typography>
            </Box>
          )}
        </Collapse>
      )}
    </>
  );
}

// --- Search results (flat list) ---

function SearchResults({
  query,
  onViewDetail,
}: {
  query: string;
  onViewDetail: (code: string) => void;
}) {
  const { data: results, isLoading, isError, refetch } = useNaicsSearch(query);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (!results || results.length === 0) {
    return (
      <EmptyState
        title="No matches"
        message={`No NAICS codes or titles matched "${query}".`}
      />
    );
  }

  return (
    <Paper variant="outlined">
      <List disablePadding>
        {results.map((r) => (
          <ListItem
            key={r.code}
            disablePadding
            secondaryAction={
              <Tooltip title="View size standard detail">
                <IconButton
                  edge="end"
                  size="small"
                  aria-label={`View detail for ${r.code}`}
                  onClick={() => onViewDetail(r.code)}
                >
                  <InfoOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            }
          >
            <ListItemButton onClick={() => onViewDetail(r.code)} sx={{ py: 0.75 }}>
              <Chip
                label={r.code}
                size="small"
                variant="outlined"
                sx={{ mr: 1.5, fontFamily: 'monospace', flexShrink: 0 }}
              />
              <ListItemText
                primary={r.title}
                slotProps={{ primary: { sx: { fontSize: '0.875rem' } } }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Paper>
  );
}

// --- Leaf / code detail dialog ---

function formatSizeStandard(detail: NaicsDetailDto): string {
  if (detail.sizeStandard == null) return 'Not available';
  const type = (detail.sizeType ?? '').toLowerCase();
  if (type.includes('employee') || type.includes('emp')) {
    return `${formatNumber(detail.sizeStandard)} employees`;
  }
  // Revenue-based standards are stored in millions of dollars.
  return `${formatCurrency(detail.sizeStandard * 1_000_000, true)} annual revenue`;
}

function NaicsDetailDialog({
  code,
  onClose,
}: {
  code: string | null;
  onClose: () => void;
}) {
  const open = code !== null;
  const { data, isLoading, isError, refetch } = useNaicsDetail(code ?? '', open);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        NAICS {code}
        {data?.title && (
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
            {data.title}
          </Typography>
        )}
      </DialogTitle>
      <DialogContent dividers>
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        ) : isError ? (
          <ErrorState
            message="Could not load NAICS detail."
            onRetry={() => refetch()}
          />
        ) : data ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <DetailRow label="Code" value={data.code} mono />
            <Divider />
            <DetailRow label="SBA Size Standard" value={formatSizeStandard(data)} />
            {data.sizeType && <DetailRow label="Size Basis" value={data.sizeType} />}
            {data.industryDescription && (
              <>
                <Divider />
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Industry Description
                  </Typography>
                  <Typography variant="body2">{data.industryDescription}</Typography>
                </Box>
              </>
            )}
          </Box>
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontWeight: 500, fontFamily: mono ? 'monospace' : undefined, textAlign: 'right' }}
      >
        {value}
      </Typography>
    </Box>
  );
}
