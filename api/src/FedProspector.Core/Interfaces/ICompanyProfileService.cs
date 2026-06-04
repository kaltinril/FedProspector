using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Interfaces;

public interface ICompanyProfileService
{
    Task<OrgProfileDto> GetProfileAsync(int orgId);
    Task<OrgProfileDto> UpdateProfileAsync(int orgId, UpdateOrgProfileRequest request);
    Task<List<OrgNaicsDto>> GetNaicsAsync(int orgId);
    Task<List<OrgNaicsDto>> SetNaicsAsync(int orgId, List<OrgNaicsDto> naicsCodes);
    Task<List<OrgCertificationDto>> GetCertificationsAsync(int orgId);
    Task<List<OrgCertificationDto>> SetCertificationsAsync(int orgId, List<OrgCertificationDto> certifications);
    Task<List<OrgPastPerformanceDto>> GetPastPerformancesAsync(int orgId);
    Task<OrgPastPerformanceDto> AddPastPerformanceAsync(int orgId, CreatePastPerformanceRequest request);
    Task<bool> DeletePastPerformanceAsync(int orgId, int id);
    Task<List<NaicsSearchDto>> SearchNaicsAsync(string query);
    Task<NaicsDetailDto?> GetNaicsDetailAsync(string code);
    Task<List<string>> GetCertificationTypesAsync();

    // --- NAICS hierarchy browsing (Phase 129 Unit B) ---

    /// <summary>Top-level 2-digit NAICS sectors, ordered by code.</summary>
    Task<List<NaicsHierarchyNodeDto>> GetNaicsSectorsAsync();

    /// <summary>Immediate children (next level down) of the given NAICS code via parent_code.</summary>
    Task<List<NaicsHierarchyNodeDto>> GetNaicsChildrenAsync(string code);

    /// <summary>The chain of ancestors from the given code up to its sector, ordered sector-first (for breadcrumbs).</summary>
    Task<List<NaicsHierarchyNodeDto>> GetNaicsAncestorsAsync(string code);

    // --- Size-eligibility engine (Phase 129 Unit B) ---

    /// <summary>
    /// Evaluates whether the organization qualifies as "small" under the SBA size
    /// standard for the given NAICS code. Side-effect free; never throws on missing inputs.
    /// </summary>
    Task<SizeEligibilityResultDto> CheckSizeEligibilityAsync(int orgId, string naicsCode);

    /// <summary>
    /// Batch size-eligibility check for many NAICS codes against one organization.
    /// Loads the org once to avoid N+1 when annotating many opportunities.
    /// Returns a dictionary keyed by NAICS code.
    /// </summary>
    Task<Dictionary<string, SizeEligibilityResultDto>> CheckSizeEligibilityAsync(int orgId, IEnumerable<string> naicsCodes);

    // --- Affiliation-aware size roll-up (Phase 133 Task 6, 13 CFR 121.103) ---

    /// <summary>
    /// Affiliation-aware size determination. Returns BOTH the standalone (org-only) verdict and the
    /// rolled-up verdict that combines the org's own receipts/headcount with each included affiliate's.
    /// Included set = active organization_entity links with relationship in { SELF, SISTER_SUBSIDIARY,
    /// JV_PARTNER }; TEAMING is excluded, and a JV_PARTNER flagged mpa_approved = 'Y' is excluded (the
    /// mentor's size is not counted). Missing affiliate figures are reported as gaps, not treated as zero.
    /// Additive to <see cref="CheckSizeEligibilityAsync(int, string)"/>; never throws on missing inputs.
    /// </summary>
    Task<AffiliatedSizeEligibilityResultDto> CheckSizeEligibilityWithAffiliatesAsync(int orgId, string naicsCode);
}
