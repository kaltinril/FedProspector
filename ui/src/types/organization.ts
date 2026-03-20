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
  legalBusinessName?: string | null;
  dbaName?: string | null;
  cageCode?: string | null;
  registrationStatus?: string | null;
  primaryNaics?: string | null;
  naicsCount: number;
  certificationCount: number;
}

/** Link entity request matching C# LinkEntityRequest */
export interface LinkEntityRequest {
  ueiSam: string;
  partnerUei?: string | null;
  relationship: string;
  notes?: string | null;
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
}
