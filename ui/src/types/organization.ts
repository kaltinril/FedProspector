/** Organization DTO matching C# OrganizationDto */
export interface OrganizationDto {
  id: number;
  name: string;
  slug: string;
  isActive: boolean;
  maxUsers: number;
  subscriptionTier?: string | null;
  createdAt: string;
}

/** Update organization request matching C# UpdateOrganizationRequest */
export interface UpdateOrganizationRequest {
  name?: string | null;
}

/** Organization member matching C# OrganizationMemberDto */
export interface OrganizationMemberDto {
  userId: number;
  email?: string | null;
  displayName: string;
  orgRole: string;
  isActive: boolean;
  createdAt?: string | null;
}

/** Invite DTO matching C# InviteDto */
export interface InviteDto {
  inviteId: number;
  email: string;
  orgRole: string;
  invitedByName?: string | null;
  expiresAt: string;
  createdAt: string;
}

/** Create invite request matching C# CreateInviteRequest */
export interface CreateInviteRequest {
  email?: string | null;
  orgRole?: string | null;
}

/** Create user request matching C# CreateUserRequest */
export interface CreateUserRequest {
  email: string;
  displayName: string;
  password: string;
  orgRole: string;
}

/** Org profile matching C# OrgProfileDto */
export interface OrgProfileDto {
  id: number;
  name: string;
  legalName?: string | null;
  dbaName?: string | null;
  ueiSam?: string | null;
  cageCode?: string | null;
  ein?: string | null;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  stateCode?: string | null;
  zipCode?: string | null;
  countryCode?: string | null;
  phone?: string | null;
  website?: string | null;
  employeeCount?: number | null;
  annualRevenue?: number | null;
  fiscalYearEndMonth?: number | null;
  entityStructure?: string | null;
  profileCompleted: boolean;
  profileCompletedAt?: string | null;
  naicsCodes: OrgNaicsDto[];
  certifications: OrgCertificationDto[];
}

/** Update org profile request matching C# UpdateOrgProfileRequest */
export interface UpdateOrgProfileRequest {
  name?: string | null;
  legalName?: string | null;
  dbaName?: string | null;
  ueiSam?: string | null;
  cageCode?: string | null;
  ein?: string | null;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  stateCode?: string | null;
  zipCode?: string | null;
  countryCode?: string | null;
  phone?: string | null;
  website?: string | null;
  employeeCount?: number | null;
  annualRevenue?: number | null;
  fiscalYearEndMonth?: number | null;
  entityStructure?: string | null;
  profileCompleted?: boolean | null;
}

/** Org NAICS code matching C# OrgNaicsDto */
export interface OrgNaicsDto {
  id?: number | null;
  naicsCode: string;
  isPrimary: boolean;
  sizeStandardMet: boolean;
}

/** Org certification matching C# OrgCertificationDto */
export interface OrgCertificationDto {
  id?: number | null;
  certificationType: string;
  certifyingAgency?: string | null;
  certificationNumber?: string | null;
  expirationDate?: string | null;
  isActive: boolean;
  source?: string | null;
}

/** Org past performance matching C# OrgPastPerformanceDto */
export interface OrgPastPerformanceDto {
  id: number;
  contractNumber?: string | null;
  agencyName?: string | null;
  description?: string | null;
  naicsCode?: string | null;
  contractValue?: number | null;
  periodStart?: string | null;
  periodEnd?: string | null;
  createdAt: string;
}

/** Create past performance request matching C# CreatePastPerformanceRequest */
export interface CreatePastPerformanceRequest {
  contractNumber?: string | null;
  agencyName?: string | null;
  description?: string | null;
  naicsCode?: string | null;
  contractValue?: number | null;
  periodStart?: string | null;
  periodEnd?: string | null;
}

/** NAICS search result matching C# NaicsSearchDto */
export interface NaicsSearchDto {
  code: string;
  title: string;
}

/** Organization entity link matching C# OrganizationEntityDto */
export interface OrganizationEntityDto {
  id: number;
  ueiSam: string;
  partnerUei?: string | null;
  relationship: string;
  isActive: boolean;
  notes?: string | null;
  addedByName?: string | null;
  createdAt: string;
  /** Phase 133 Task 6: owner-entered affiliate annual receipts (raw USD). */
  affiliateAnnualRevenue?: number | null;
  /** Phase 133 Task 6: owner-entered affiliate employee count. */
  affiliateEmployeeCount?: number | null;
  /** Phase 133 Task 6: true when this JV_PARTNER link is an SBA-approved mentor-protégé agreement. */
  mpaApproved: boolean;
  /** Phase 133 Task 6: effective date of the approved mentor-protégé agreement (ISO date). */
  mpaEffectiveDate?: string | null;
  legalBusinessName?: string | null;
  dbaName?: string | null;
  cageCode?: string | null;
  registrationStatus?: string | null;
  primaryNaics?: string | null;
  naicsCount: number;
  certificationCount: number;
}

// --- Phase 136 Unit F: edit an existing linked entity at any time ---

/** Update linked-entity request matching C# UpdateEntityLinkRequest. */
export interface UpdateEntityLinkRequest {
  affiliateAnnualRevenue?: number | null;
  affiliateEmployeeCount?: number | null;
  mpaApproved?: boolean | null;
  mpaEffectiveDate?: string | null;
  notes?: string | null;
  partnerUei?: string | null;
}

// --- Phase 136 Unit G: associated NAICS (manual list) ---

/** Associated NAICS matching C# OrgAssociatedNaicsDto. */
export interface OrgAssociatedNaicsDto {
  id: number;
  naicsCode: string;
  note?: string | null;
  createdAt: string;
  /**
   * Phase 136 follow-up: true when an add matched a code already on the associated list (the
   * add was idempotent). Lets the UI show "already added" instead of a fresh-add success.
   */
  alreadyExisted?: boolean;
}

/** Add associated NAICS request matching C# CreateAssociatedNaicsRequest. */
export interface CreateAssociatedNaicsRequest {
  naicsCode: string;
  note?: string | null;
}

/** Link entity request matching C# LinkEntityRequest */
export interface LinkEntityRequest {
  ueiSam: string;
  partnerUei?: string | null;
  relationship: string;
  notes?: string | null;
  /** Phase 133 Task 6: owner-entered affiliate annual receipts (raw USD). */
  affiliateAnnualRevenue?: number | null;
  /** Phase 133 Task 6: owner-entered affiliate employee count. */
  affiliateEmployeeCount?: number | null;
  /** Phase 133 Task 6: SBA-approved mentor-protégé agreement flag (JV_PARTNER only). */
  mpaApproved?: boolean | null;
  /** Phase 133 Task 6: effective date of the approved mentor-protégé agreement (ISO date). */
  mpaEffectiveDate?: string | null;
}

/** Affiliation-aware size determination matching C# AffiliatedSizeEligibilityResultDto (Phase 133 Task 6). */
export interface AffiliatedSizeEligibilityResultDto {
  naicsCode: string;
  sizeType?: string | null;
  threshold?: number | null;
  standaloneEligible?: boolean | null;
  affiliatedEligible?: boolean | null;
  combinedRevenue?: number | null;
  combinedEmployees?: number | null;
  affiliateCount: number;
  includedAffiliates: IncludedAffiliateDto[];
  excludedAffiliates: ExcludedAffiliateDto[];
  missingAffiliateData: string[];
  flippedToOtherThanSmall: boolean;
  reason: string;
}

/** An affiliate counted in the size roll-up, matching C# IncludedAffiliateDto. */
export interface IncludedAffiliateDto {
  uei: string;
  relationship: string;
  contributedAmount?: number | null;
}

/** An affiliate excluded from the size roll-up, matching C# ExcludedAffiliateDto. */
export interface ExcludedAffiliateDto {
  uei: string;
  relationship: string;
  /** "APPROVED_MPA" or "TEAMING". */
  reason: string;
}

/** Refresh self entity response matching C# RefreshSelfEntityResponse */
export interface RefreshSelfEntityResponse {
  naicsCopied: number;
  certificationsCopied: number;
  profileUpdated: boolean;
  message: string;
}

/** NAICS detail matching C# NaicsDetailDto */
export interface NaicsDetailDto {
  code: string;
  title: string;
  sizeStandard?: number | null;
  sizeType?: string | null;
  industryDescription?: string | null;
  /** Phase 129 Unit F: SBA size-standard footnotes (empty when none). */
  footnotes: NaicsFootnote[];
}

// --- Phase 129 NAICS footnotes (Unit F) ---

/** NAICS size-standard footnote/exception matching C# NaicsFootnoteDto */
export interface NaicsFootnote {
  footnoteId: string;
  section: string;
  description: string;
}

// --- Phase 129 NAICS hierarchy (Unit E) ---

/** A node in the NAICS taxonomy tree, matching C# NaicsHierarchyNodeDto. */
export interface NaicsHierarchyNode {
  code: string;
  title: string;
  level?: number | null;
  levelName?: string | null;
  parentCode?: string | null;
  isLeaf: boolean;
}
