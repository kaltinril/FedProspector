import { useCallback, useState } from 'react';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Badge from '@mui/material/Badge';
import Typography from '@mui/material/Typography';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import AccountBalanceOutlined from '@mui/icons-material/AccountBalanceOutlined';
import BusinessOutlined from '@mui/icons-material/BusinessOutlined';
import StoreOutlined from '@mui/icons-material/StoreOutlined';

import { useHierarchyTree, useHierarchyChildren } from '@/queries/useHierarchy';
import type { FederalOrgTreeNode, FederalOrgListItem } from '@/types/api';

interface HierarchyTreeProps {
  selectedId?: string;
  status?: string;
  keyword?: string;
  onSelect: (fhOrgId: string, name: string) => void;
}

// ---------------------------------------------------------------------------
// Child node (lazy-loaded on expand)
// ---------------------------------------------------------------------------

function TreeNode({
  fhOrgId,
  name,
  childCount,
  level,
  selectedId,
  status,
  keyword,
  onSelect,
}: {
  fhOrgId: string;
  name: string;
  childCount: number;
  level: number;
  selectedId?: string;
  status?: string;
  keyword?: string;
  onSelect: (fhOrgId: string, name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const { data: children, isLoading } = useHierarchyChildren(fhOrgId, open, status, keyword);

  const hasChildren = childCount > 0;
  const isSelected = selectedId === fhOrgId;

  const handleToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setOpen((prev) => !prev);
    },
    [],
  );

  const handleSelect = useCallback(() => {
    onSelect(fhOrgId, name);
  }, [fhOrgId, name, onSelect]);

  const icon =
    level <= 1 ? (
      <AccountBalanceOutlined fontSize="small" />
    ) : level === 2 ? (
      <BusinessOutlined fontSize="small" />
    ) : (
      <StoreOutlined fontSize="small" />
    );

  return (
    <>
      <ListItemButton
        selected={isSelected}
        onClick={handleSelect}
        sx={{ pl: 2 + level * 2, py: 0.5, borderRadius: 1, mx: 0.5, mb: 0.25 }}
      >
        <ListItemIcon sx={{ minWidth: 32 }}>{icon}</ListItemIcon>
        <ListItemText
          primary={name}
          primaryTypographyProps={{
            variant: 'body2',
            noWrap: false,
            fontWeight: isSelected ? 600 : 400,
          }}
        />
        {hasChildren && (
          <Badge
            badgeContent={childCount}
            color="default"
            max={999}
            sx={{ mr: 1, '& .MuiBadge-badge': { fontSize: '0.65rem' } }}
          />
        )}
        {hasChildren && (
          <Box
            component="span"
            onClick={handleToggle}
            sx={{ display: 'flex', alignItems: 'center', ml: 0.5 }}
          >
            {isLoading ? (
              <CircularProgress size={16} />
            ) : open ? (
              <ExpandLess fontSize="small" />
            ) : (
              <ExpandMore fontSize="small" />
            )}
          </Box>
        )}
      </ListItemButton>

      {hasChildren && (
        <Collapse in={open} timeout="auto" unmountOnExit>
          <List disablePadding>
            {(children ?? []).map((child: FederalOrgListItem) => (
              <TreeNode
                key={child.fhOrgId}
                fhOrgId={child.fhOrgId}
                name={child.fhOrgName}
                childCount={child.childCount ?? 0}
                level={level + 1}
                selectedId={selectedId}
                status={status}
                keyword={keyword}
                onSelect={onSelect}
              />
            ))}
          </List>
        </Collapse>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main tree component
// ---------------------------------------------------------------------------

export function HierarchyTree({ selectedId, status, keyword, onSelect }: HierarchyTreeProps) {
  const { data: departments, isLoading } = useHierarchyTree(keyword);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!departments || departments.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
        No departments found.
      </Typography>
    );
  }

  return (
    <List disablePadding dense>
      {departments.map((dept: FederalOrgTreeNode) => (
        <TreeNode
          key={dept.fhOrgId}
          fhOrgId={dept.fhOrgId}
          name={dept.fhOrgName}
          childCount={dept.childCount}
          level={0}
          selectedId={selectedId}
          status={status}
          keyword={keyword}
          onSelect={onSelect}
        />
      ))}
    </List>
  );
}
