export const queryKeys = {
  opportunities: {
    all: ['opportunities'] as const,
    list: (params: Record<string, unknown>) => ['opportunities', 'list', params] as const,
    detail: (noticeId: string) => ['opportunities', 'detail', noticeId] as const,
    targets: (params: Record<string, unknown>) => ['opportunities', 'targets', params] as const,
  },
  awards: {
    all: ['awards'] as const,
    list: (params: Record<string, unknown>) => ['awards', 'list', params] as const,
    detail: (contractId: string) => ['awards', 'detail', contractId] as const,
    burnRate: (contractId: string) => ['awards', 'burnRate', contractId] as const,
  },
  entities: {
    all: ['entities'] as const,
    list: (params: Record<string, unknown>) => ['entities', 'list', params] as const,
    detail: (uei: string) => ['entities', 'detail', uei] as const,
    competitor: (uei: string) => ['entities', 'competitor', uei] as const,
    exclusions: (uei: string) => ['entities', 'exclusions', uei] as const,
  },
  subawards: {
    all: ['subawards'] as const,
    teamingPartners: (params: Record<string, unknown>) =>
      ['subawards', 'teamingPartners', params] as const,
  },
  prospects: {
    all: ['prospects'] as const,
    list: (params: Record<string, unknown>) => ['prospects', 'list', params] as const,
    detail: (id: number) => ['prospects', 'detail', id] as const,
  },
  proposals: {
    all: ['proposals'] as const,
    list: (params: Record<string, unknown>) => ['proposals', 'list', params] as const,
    milestones: (proposalId: number) => ['proposals', 'milestones', proposalId] as const,
  },
  dashboard: {
    all: ['dashboard'] as const,
  },
  savedSearches: {
    all: ['savedSearches'] as const,
    list: ['savedSearches', 'list'] as const,
    detail: (id: number) => ['savedSearches', 'detail', id] as const,
    run: (id: number) => ['savedSearches', 'run', id] as const,
  },
  notifications: {
    all: ['notifications'] as const,
    list: (params: Record<string, unknown>) => ['notifications', 'list', params] as const,
    unreadCount: ['notifications', 'unreadCount'] as const,
  },
  admin: {
    all: ['admin'] as const,
    etlStatus: ['admin', 'etlStatus'] as const,
    users: (params?: Record<string, unknown>) => ['admin', 'users', params] as const,
  },
  organization: {
    all: ['organization'] as const,
    details: ['organization', 'details'] as const,
    profile: ['organization', 'profile'] as const,
    naics: ['organization', 'naics'] as const,
    certifications: ['organization', 'certifications'] as const,
    pastPerformance: ['organization', 'pastPerformance'] as const,
    members: ['organization', 'members'] as const,
    invites: ['organization', 'invites'] as const,
  },
  reference: {
    naics: (query: string) => ['reference', 'naics', query] as const,
    naicsDetail: (code: string) => ['reference', 'naics', 'detail', code] as const,
    certificationTypes: ['reference', 'certificationTypes'] as const,
  },
  auth: {
    me: ['auth', 'me'] as const,
  },
} as const;
