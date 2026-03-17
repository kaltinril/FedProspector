using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Entities;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class EntityService : IEntityService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<EntityService> _logger;

    public EntityService(FedProspectorDbContext context, ILogger<EntityService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<EntitySearchDto>> SearchAsync(EntitySearchRequest request)
    {
        var query = _context.Entities.AsNoTracking().AsQueryable();

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.Name))
        {
            var escapedName = EscapeLikePattern(request.Name);
            // Leading-wildcard LIKE can't use the B-tree index; tell MySQL not to
            // attempt an ordered index scan (which is far slower than a table scan).
            query = query
                .TagWith("HINT:NO_INDEX(entity idx_entity_name)")
                .Where(e => EF.Functions.Like(e.LegalBusinessName, $"%{escapedName}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.Uei))
            query = query.Where(e => e.UeiSam == request.Uei);

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(e => _context.EntityNaicsCodes.Any(n => n.UeiSam == e.UeiSam && n.NaicsCode == request.Naics));

        if (!string.IsNullOrWhiteSpace(request.RegistrationStatus))
            query = query.Where(e => e.RegistrationStatus == request.RegistrationStatus);

        // State filter: Entity has no direct State column; use EXISTS on EntityAddresses
        if (!string.IsNullOrWhiteSpace(request.State))
            query = query.Where(e => _context.EntityAddresses.Any(a => a.UeiSam == e.UeiSam && a.StateOrProvince == request.State));

        // BusinessType filter: EXISTS subquery on EntityBusinessTypes
        if (!string.IsNullOrWhiteSpace(request.BusinessType))
            query = query.Where(e => _context.EntityBusinessTypes.Any(bt => bt.UeiSam == e.UeiSam && bt.BusinessTypeCode == request.BusinessType));

        // SbaCertification filter: EXISTS subquery on EntitySbaCertifications
        if (!string.IsNullOrWhiteSpace(request.SbaCertification))
            query = query.Where(e => _context.EntitySbaCertifications.Any(sc =>
                sc.UeiSam == e.UeiSam
                && sc.SbaTypeCode == request.SbaCertification
                && (sc.CertificationExitDate == null || sc.CertificationExitDate > DateOnly.FromDateTime(DateTime.UtcNow))));

        var totalCount = await query.CountAsync();

        // Default sort: LegalBusinessName ascending
        IOrderedQueryable<Core.Models.Entity> ordered = query.OrderBy(e => e.LegalBusinessName);

        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            ordered = request.SortBy.ToLowerInvariant() switch
            {
                "name" or "legalbusinessname" => request.SortDescending ? query.OrderByDescending(e => e.LegalBusinessName) : query.OrderBy(e => e.LegalBusinessName),
                "dbaname" => request.SortDescending ? query.OrderByDescending(e => e.DbaName) : query.OrderBy(e => e.DbaName),
                "ueisam" => request.SortDescending ? query.OrderByDescending(e => e.UeiSam) : query.OrderBy(e => e.UeiSam),
                "primarynaics" => request.SortDescending ? query.OrderByDescending(e => e.PrimaryNaics) : query.OrderBy(e => e.PrimaryNaics),
                "registrationstatus" => request.SortDescending ? query.OrderByDescending(e => e.RegistrationStatus) : query.OrderBy(e => e.RegistrationStatus),
                "entityurl" => request.SortDescending ? query.OrderByDescending(e => e.EntityUrl) : query.OrderBy(e => e.EntityUrl),
                "lastupdatedate" => request.SortDescending ? query.OrderByDescending(e => e.LastUpdateDate) : query.OrderBy(e => e.LastUpdateDate),
                "registrationexpirationdate" => request.SortDescending ? query.OrderByDescending(e => e.RegistrationExpirationDate) : query.OrderBy(e => e.RegistrationExpirationDate),
                _ => ordered
            };
        }

        // Project to DTO; derive PopState via LEFT JOIN to physical address
        var enriched = from e in ordered
            join a in _context.EntityAddresses.Where(a => a.AddressType == "PHYSICAL")
                on e.UeiSam equals a.UeiSam into addrJoin
            from a in addrJoin.DefaultIfEmpty()
            select new { Entity = e, PopState = a != null ? a.StateOrProvince : null };

        var items = await enriched
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .Select(x => new EntitySearchDto
            {
                UeiSam = x.Entity.UeiSam,
                LegalBusinessName = x.Entity.LegalBusinessName,
                DbaName = x.Entity.DbaName,
                RegistrationStatus = x.Entity.RegistrationStatus,
                PrimaryNaics = x.Entity.PrimaryNaics,
                EntityStructureCode = x.Entity.EntityStructureCode,
                PopState = x.PopState,
                EntityUrl = x.Entity.EntityUrl,
                LastUpdateDate = x.Entity.LastUpdateDate,
                RegistrationExpirationDate = x.Entity.RegistrationExpirationDate
            })
            .ToListAsync();

        return new PagedResponse<EntitySearchDto>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<EntityDetailDto?> GetDetailAsync(string uei)
    {
        var entity = await _context.Entities.AsNoTracking()
            .FirstOrDefaultAsync(e => e.UeiSam == uei);

        if (entity == null) return null;

        // Fetch child collections sequentially (EF Core DbContext is not thread-safe)
        var addresses = await (from a in _context.EntityAddresses.AsNoTracking()
                where a.UeiSam == uei
                join cc in _context.RefCountryCodes on a.CountryCode equals cc.ThreeCode into countryJoin
                from cc in countryJoin.DefaultIfEmpty()
                select new EntityAddressDto
                {
                    AddressType = a.AddressType,
                    AddressLine1 = a.AddressLine1,
                    AddressLine2 = a.AddressLine2,
                    City = a.City,
                    StateOrProvince = a.StateOrProvince,
                    ZipCode = a.ZipCode,
                    CountryCode = a.CountryCode,
                    CountryName = cc != null ? cc.CountryName : a.CountryCode,
                    CongressionalDistrict = a.CongressionalDistrict
                })
            .ToListAsync();

        var naics = await (from n in _context.EntityNaicsCodes.AsNoTracking()
                where n.UeiSam == uei
                join r in _context.RefNaicsCodes on n.NaicsCode equals r.NaicsCode into refJoin
                from r in refJoin.DefaultIfEmpty()
                select new EntityNaicsDto
                {
                    NaicsCode = n.NaicsCode,
                    NaicsDescription = r != null ? r.Description : null,
                    IsPrimary = n.IsPrimary,
                    SbaSmallBusiness = n.SbaSmallBusiness
                })
            .ToListAsync();

        var psc = await (from p in _context.EntityPscCodes.AsNoTracking()
                where p.UeiSam == uei
                join r in _context.RefPscCodeLatest on p.PscCode equals r.PscCode into pscJoin
                from r in pscJoin.DefaultIfEmpty()
                select new EntityPscDto
                {
                    PscCode = p.PscCode,
                    PscDescription = r != null ? r.PscName : null
                })
            .ToListAsync();

        var businessTypes = await (from bt in _context.EntityBusinessTypes.AsNoTracking()
                where bt.UeiSam == uei
                join r in _context.RefBusinessTypes on bt.BusinessTypeCode equals r.BusinessTypeCode into refJoin
                from r in refJoin.DefaultIfEmpty()
                select new EntityBusinessTypeDto
                {
                    BusinessTypeCode = bt.BusinessTypeCode,
                    BusinessTypeDescription = r != null ? r.Description : null
                })
            .ToListAsync();

        var sbaCerts = await _context.EntitySbaCertifications.AsNoTracking()
            .Where(sc => sc.UeiSam == uei)
            .Select(sc => new EntitySbaCertificationDto
            {
                SbaTypeCode = sc.SbaTypeCode,
                SbaTypeDesc = sc.SbaTypeDesc,
                CertificationEntryDate = sc.CertificationEntryDate,
                CertificationExitDate = sc.CertificationExitDate
            })
            .ToListAsync();

        var pocs = await _context.EntityPocs.AsNoTracking()
            .Where(pc => pc.UeiSam == uei)
            .Select(pc => new EntityPocDto
            {
                PocType = pc.PocType,
                FirstName = pc.FirstName,
                MiddleInitial = pc.MiddleInitial,
                LastName = pc.LastName,
                Title = pc.Title,
                City = pc.City,
                StateOrProvince = pc.StateOrProvince,
                CountryCode = pc.CountryCode
            })
            .ToListAsync();

        return new EntityDetailDto
        {
            UeiSam = entity.UeiSam,
            UeiDuns = entity.UeiDuns,
            CageCode = entity.CageCode,
            LegalBusinessName = entity.LegalBusinessName,
            DbaName = entity.DbaName,
            RegistrationStatus = entity.RegistrationStatus,
            InitialRegistrationDate = entity.InitialRegistrationDate,
            RegistrationExpirationDate = entity.RegistrationExpirationDate,
            LastUpdateDate = entity.LastUpdateDate,
            ActivationDate = entity.ActivationDate,
            EntityStructureCode = entity.EntityStructureCode,
            PrimaryNaics = entity.PrimaryNaics,
            EntityUrl = entity.EntityUrl,
            StateOfIncorporation = entity.StateOfIncorporation,
            CountryOfIncorporation = entity.CountryOfIncorporation,
            ExclusionStatusFlag = entity.ExclusionStatusFlag,
            EftIndicator = entity.EftIndicator,
            Addresses = addresses,
            NaicsCodes = naics,
            PscCodes = psc,
            BusinessTypes = businessTypes,
            SbaCertifications = sbaCerts,
            PointsOfContact = pocs
        };
    }

    public async Task<CompetitorProfileDto?> GetCompetitorProfileAsync(string uei)
    {
        var competitor = await _context.CompetitorAnalyses.AsNoTracking()
            .FirstOrDefaultAsync(c => c.UeiSam == uei);

        if (competitor == null) return null;

        return new CompetitorProfileDto
        {
            UeiSam = competitor.UeiSam,
            LegalBusinessName = competitor.LegalBusinessName,
            PrimaryNaics = competitor.PrimaryNaics,
            NaicsDescription = competitor.NaicsDescription,
            NaicsSector = competitor.NaicsSector,
            EntityStructure = competitor.EntityStructure,
            BusinessTypes = competitor.BusinessTypes,
            BusinessTypeCategories = competitor.BusinessTypeCategories,
            SbaCertifications = competitor.SbaCertifications,
            PastContracts = competitor.PastContracts,
            TotalObligated = competitor.TotalObligated,
            MostRecentAward = competitor.MostRecentAward
        };
    }

    public async Task<ExclusionCheckDto> CheckExclusionAsync(string uei)
    {
        // Look up the entity name for fuzzy matching
        var entity = await _context.Entities.AsNoTracking()
            .FirstOrDefaultAsync(e => e.UeiSam == uei);

        var entityName = entity?.LegalBusinessName;

        // Query active exclusions: by UEI, or by entity name if available
        var exclusionQuery = _context.SamExclusions.AsNoTracking()
            .Where(ex => (ex.TerminationDate == null || ex.TerminationDate > DateOnly.FromDateTime(DateTime.UtcNow)));

        if (!string.IsNullOrWhiteSpace(entityName))
        {
            exclusionQuery = exclusionQuery.Where(ex => ex.Uei == uei
                || (ex.EntityName != null && ex.EntityName.Contains(entityName)));
        }
        else
        {
            exclusionQuery = exclusionQuery.Where(ex => ex.Uei == uei);
        }

        var exclusions = await exclusionQuery
            .Select(ex => new ExclusionDto
            {
                ExclusionType = ex.ExclusionType,
                ExclusionProgram = ex.ExclusionProgram,
                ExcludingAgencyName = ex.ExcludingAgencyName,
                ActivationDate = ex.ActivationDate,
                TerminationDate = ex.TerminationDate,
                AdditionalComments = ex.AdditionalComments
            })
            .ToListAsync();

        return new ExclusionCheckDto
        {
            Uei = uei,
            EntityName = entityName,
            IsExcluded = exclusions.Count > 0,
            ActiveExclusions = exclusions,
            CheckedAt = DateTime.UtcNow
        };
    }

    /// <summary>
    /// Escapes LIKE special characters (%, _, \) so user input is treated as literals.
    /// </summary>
    private static string EscapeLikePattern(string input)
    {
        if (string.IsNullOrEmpty(input)) return input;
        return input.Replace("\\", "\\\\").Replace("%", "\\%").Replace("_", "\\_");
    }
}
