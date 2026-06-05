import apiClient from './client';
import type {
  OrganizationDto,
  UpdateOrganizationRequest,
  OrganizationMemberDto,
  InviteDto,
  CreateInviteRequest,
  CreateUserRequest,
  OrgProfileDto,
  UpdateOrgProfileRequest,
  OrgNaicsDto,
  OrgCertificationDto,
  OrgPastPerformanceDto,
  CreatePastPerformanceRequest,
  NaicsSearchDto,
  NaicsDetailDto,
  OrganizationEntityDto,
  LinkEntityRequest,
  UpdateEntityLinkRequest,
  RefreshSelfEntityResponse,
  NaicsHierarchyNode,
  AffiliatedSizeEligibilityResultDto,
  OrgAssociatedNaicsDto,
  CreateAssociatedNaicsRequest,
} from '@/types/organization';

// Organization management
export function getOrganization(): Promise<OrganizationDto> {
  return apiClient.get('/org').then((r) => r.data);
}

export function updateOrganization(data: UpdateOrganizationRequest): Promise<OrganizationDto> {
  return apiClient.patch('/org', data).then((r) => r.data);
}

export function getMembers(): Promise<OrganizationMemberDto[]> {
  return apiClient.get('/org/members').then((r) => r.data);
}

// Invites
export function getInvites(): Promise<InviteDto[]> {
  return apiClient.get('/org/invites').then((r) => r.data);
}

export function createInvite(data: CreateInviteRequest): Promise<InviteDto> {
  return apiClient.post('/org/invites', data).then((r) => r.data);
}

export function revokeInvite(id: number): Promise<void> {
  return apiClient.delete(`/org/invites/${id}`).then((r) => r.data);
}

export function createUser(data: CreateUserRequest): Promise<OrganizationMemberDto> {
  return apiClient.post('/org/members', data).then((r) => r.data);
}

// Company profile
export function getProfile(): Promise<OrgProfileDto> {
  return apiClient.get('/org/profile').then((r) => r.data);
}

export function updateProfile(data: UpdateOrgProfileRequest): Promise<OrgProfileDto> {
  return apiClient.put('/org/profile', data).then((r) => r.data);
}

// NAICS codes
export function getNaics(): Promise<OrgNaicsDto[]> {
  return apiClient.get('/org/naics').then((r) => r.data);
}

export function setNaics(data: OrgNaicsDto[]): Promise<OrgNaicsDto[]> {
  return apiClient.put('/org/naics', data).then((r) => r.data);
}

// Associated NAICS (Phase 136 Unit G)
export function getAssociatedNaics(): Promise<OrgAssociatedNaicsDto[]> {
  return apiClient.get('/org/associated-naics').then((r) => r.data);
}

export function addAssociatedNaics(
  data: CreateAssociatedNaicsRequest,
): Promise<OrgAssociatedNaicsDto> {
  return apiClient.post('/org/associated-naics', data).then((r) => r.data);
}

export function deleteAssociatedNaics(id: number): Promise<void> {
  return apiClient.delete(`/org/associated-naics/${id}`).then((r) => r.data);
}

// Certifications
export function getCertifications(): Promise<OrgCertificationDto[]> {
  return apiClient.get('/org/certifications').then((r) => r.data);
}

export function setCertifications(data: OrgCertificationDto[]): Promise<OrgCertificationDto[]> {
  return apiClient.put('/org/certifications', data).then((r) => r.data);
}

// Past performance
export function getPastPerformance(): Promise<OrgPastPerformanceDto[]> {
  return apiClient.get('/org/past-performance').then((r) => r.data);
}

export function createPastPerformance(
  data: CreatePastPerformanceRequest,
): Promise<OrgPastPerformanceDto> {
  return apiClient.post('/org/past-performance', data).then((r) => r.data);
}

export function deletePastPerformance(id: number): Promise<void> {
  return apiClient.delete(`/org/past-performance/${id}`).then((r) => r.data);
}

// Reference data
export function searchNaics(q: string): Promise<NaicsSearchDto[]> {
  return apiClient.get('/reference/naics', { params: { q } }).then((r) => r.data);
}

export function getNaicsDetail(code: string): Promise<NaicsDetailDto> {
  return apiClient.get(`/reference/naics/${encodeURIComponent(code)}`).then((r) => r.data);
}

export function getCertificationTypes(): Promise<string[]> {
  return apiClient.get('/reference/certifications').then((r) => r.data);
}

// Entity linking (Phase 91)
export function getLinkedEntities(): Promise<OrganizationEntityDto[]> {
  return apiClient.get('/org/entities').then((r) => r.data);
}

export function linkEntity(data: LinkEntityRequest): Promise<OrganizationEntityDto> {
  return apiClient.post('/org/entities', data).then((r) => r.data);
}

export function deactivateEntityLink(linkId: number): Promise<void> {
  return apiClient.delete(`/org/entities/${linkId}`).then((r) => r.data);
}

// Phase 136 Unit F: update an existing linked entity's editable data at any time.
export function updateEntityLink(
  linkId: number,
  data: UpdateEntityLinkRequest,
): Promise<OrganizationEntityDto> {
  return apiClient.put(`/org/entities/${linkId}`, data).then((r) => r.data);
}

export function refreshSelfEntity(): Promise<RefreshSelfEntityResponse> {
  return apiClient.post('/org/entities/refresh-self').then((r) => r.data);
}

export function getAggregateNaics(): Promise<string[]> {
  return apiClient.get('/org/entities/aggregate-naics').then((r) => r.data);
}

// --- Phase 133 Task 6: affiliation-aware size determination ---

/** Affiliation-aware SBA size determination for a NAICS code (standalone + rolled-up). */
export function getAffiliatedSizeEligibility(
  naicsCode: string,
): Promise<AffiliatedSizeEligibilityResultDto> {
  return apiClient
    .get(`/org/size-eligibility/${encodeURIComponent(naicsCode)}`)
    .then((r) => r.data);
}

// --- Phase 129 NAICS hierarchy (Unit E) ---

/** Top-level 2-digit NAICS sectors (root of the hierarchy tree). */
export function getNaicsSectors(): Promise<NaicsHierarchyNode[]> {
  return apiClient.get('/reference/naics/sectors').then((r) => r.data);
}

/** Immediate children (next level down) of a NAICS code. */
export function getNaicsChildren(code: string): Promise<NaicsHierarchyNode[]> {
  return apiClient
    .get(`/reference/naics/${encodeURIComponent(code)}/children`)
    .then((r) => r.data);
}

/** Ancestor chain (sector -> code) for breadcrumbs. */
export function getNaicsAncestors(code: string): Promise<NaicsHierarchyNode[]> {
  return apiClient
    .get(`/reference/naics/${encodeURIComponent(code)}/ancestors`)
    .then((r) => r.data);
}
