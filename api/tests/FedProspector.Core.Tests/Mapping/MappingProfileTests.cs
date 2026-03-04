using AutoMapper;
using FluentAssertions;
using FedProspector.Core.Mapping;
using FedProspector.Core.Models;
using FedProspector.Core.Models.Views;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.DTOs.Entities;
using FedProspector.Core.DTOs.SavedSearches;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Core.Tests.Mapping;

public class MappingProfileTests
{
    private readonly IMapper _mapper;
    private readonly MapperConfiguration _configuration;

    public MappingProfileTests()
    {
        var expression = new MapperConfigurationExpression();
        expression.AddProfile<MappingProfile>();
        _configuration = new MapperConfiguration(expression, NullLoggerFactory.Instance);
        _mapper = _configuration.CreateMapper();
    }

    [Fact]
    public void MappingProfile_ConfigurationIsValid()
    {
        _configuration.AssertConfigurationIsValid();
    }

    [Fact]
    public void Map_TargetOpportunityView_ToDto_ShouldMapAllProperties()
    {
        var source = new TargetOpportunityView
        {
            NoticeId = "NOTICE-001",
            Title = "Test Opportunity",
            SolicitationNumber = "SOL-123",
            DepartmentName = "DoD",
            Office = "NAVAIR",
            PostedDate = new DateOnly(2025, 6, 1),
            ResponseDeadline = new DateTime(2025, 7, 1),
            DaysUntilDue = 30,
            SetAsideCode = "SBA",
            SetAsideDescription = "Small Business",
            SetAsideCategory = "WOSB",
            NaicsCode = "541511",
            NaicsDescription = "Custom Computer Programming Services",
            NaicsLevel = "6-digit",
            NaicsSector = "54",
            SizeStandard = "$30M",
            SizeType = "Revenue",
            AwardAmount = 1000000m,
            PopState = "VA",
            PopCity = "Arlington",
            DescriptionUrl = "https://api.sam.gov/opportunities/v2/search?noticeid=123",
            Link = "https://sam.gov/opp/123",
            ProspectId = 42,
            ProspectStatus = "ACTIVE",
            ProspectPriority = "HIGH",
            AssignedTo = "John Doe"
        };

        var dto = _mapper.Map<TargetOpportunityDto>(source);

        dto.NoticeId.Should().Be("NOTICE-001");
        dto.Title.Should().Be("Test Opportunity");
        dto.DaysUntilDue.Should().Be(30);
        dto.AwardAmount.Should().Be(1000000m);
        dto.ProspectId.Should().Be(42);
    }

    [Fact]
    public void Map_CompetitorAnalysisView_ToDto_ShouldMapAllProperties()
    {
        var source = new CompetitorAnalysisView
        {
            UeiSam = "ABC123456789",
            LegalBusinessName = "Test Corp",
            PrimaryNaics = "541511",
            NaicsDescription = "Custom Computer Programming Services",
            NaicsSector = "54",
            EntityStructure = "LLC",
            BusinessTypes = "2X~27",
            BusinessTypeCategories = "Small Business~WOSB",
            SbaCertifications = "8(a)",
            PastContracts = 15,
            TotalObligated = 5000000m,
            MostRecentAward = new DateOnly(2025, 3, 15)
        };

        var dto = _mapper.Map<CompetitorProfileDto>(source);

        dto.UeiSam.Should().Be("ABC123456789");
        dto.LegalBusinessName.Should().Be("Test Corp");
        dto.PastContracts.Should().Be(15);
        dto.TotalObligated.Should().Be(5000000m);
    }

    [Fact]
    public void Map_EntityAddress_ToDto_ShouldMapCorrectly()
    {
        var source = new EntityAddress
        {
            Id = 1,
            UeiSam = "ABC123456789",
            AddressType = "PHYSICAL",
            AddressLine1 = "123 Main St",
            City = "Arlington",
            StateOrProvince = "VA",
            ZipCode = "22201",
            CountryCode = "USA",
            CongressionalDistrict = "VA-08"
        };

        var dto = _mapper.Map<EntityAddressDto>(source);

        dto.AddressType.Should().Be("PHYSICAL");
        dto.AddressLine1.Should().Be("123 Main St");
        dto.City.Should().Be("Arlington");
        dto.StateOrProvince.Should().Be("VA");
        dto.ZipCode.Should().Be("22201");
        dto.CountryCode.Should().Be("USA");
        dto.CongressionalDistrict.Should().Be("VA-08");
    }

    [Fact]
    public void Map_EntityNaics_ToDto_ShouldMapCorrectly()
    {
        var source = new EntityNaics
        {
            Id = 1,
            UeiSam = "ABC123456789",
            NaicsCode = "541511",
            IsPrimary = "Y",
            SbaSmallBusiness = "Y"
        };

        var dto = _mapper.Map<EntityNaicsDto>(source);

        dto.NaicsCode.Should().Be("541511");
        dto.IsPrimary.Should().Be("Y");
        dto.SbaSmallBusiness.Should().Be("Y");
    }

    [Fact]
    public void Map_EntityPsc_ToDto_ShouldMapCorrectly()
    {
        var source = new EntityPsc { Id = 1, UeiSam = "ABC123456789", PscCode = "R425" };

        var dto = _mapper.Map<EntityPscDto>(source);

        dto.PscCode.Should().Be("R425");
    }

    [Fact]
    public void Map_EntityBusinessType_ToDto_ShouldMapCorrectly()
    {
        var source = new EntityBusinessType { Id = 1, UeiSam = "ABC123456789", BusinessTypeCode = "2X" };

        var dto = _mapper.Map<EntityBusinessTypeDto>(source);

        dto.BusinessTypeCode.Should().Be("2X");
    }

    [Fact]
    public void Map_EntitySbaCertification_ToDto_ShouldMapCorrectly()
    {
        var source = new EntitySbaCertification
        {
            Id = 1,
            UeiSam = "ABC123456789",
            SbaTypeCode = "8A",
            SbaTypeDesc = "8(a) Business Development",
            CertificationEntryDate = new DateOnly(2020, 1, 1),
            CertificationExitDate = new DateOnly(2029, 12, 31)
        };

        var dto = _mapper.Map<EntitySbaCertificationDto>(source);

        dto.SbaTypeCode.Should().Be("8A");
        dto.SbaTypeDesc.Should().Be("8(a) Business Development");
        dto.CertificationEntryDate.Should().Be(new DateOnly(2020, 1, 1));
        dto.CertificationExitDate.Should().Be(new DateOnly(2029, 12, 31));
    }

    [Fact]
    public void Map_EntityPoc_ToDto_ShouldMapCorrectly()
    {
        var source = new EntityPoc
        {
            Id = 1,
            UeiSam = "ABC123456789",
            PocType = "GOVERNMENT_BUSINESS",
            FirstName = "Jane",
            MiddleInitial = "M",
            LastName = "Doe",
            Title = "Director",
            City = "DC",
            StateOrProvince = "DC",
            CountryCode = "USA"
        };

        var dto = _mapper.Map<EntityPocDto>(source);

        dto.PocType.Should().Be("GOVERNMENT_BUSINESS");
        dto.FirstName.Should().Be("Jane");
        dto.LastName.Should().Be("Doe");
        dto.Title.Should().Be("Director");
    }

    [Fact]
    public void Map_SamExclusion_ToDto_ShouldMapCorrectly()
    {
        var source = new SamExclusion
        {
            Id = 1,
            ExclusionType = "DEBARMENT",
            ExclusionProgram = "RECIPROCAL",
            ExcludingAgencyName = "Dept of Defense",
            ActivationDate = new DateOnly(2024, 1, 1),
            TerminationDate = new DateOnly(2027, 1, 1),
            AdditionalComments = "Test comment"
        };

        var dto = _mapper.Map<ExclusionDto>(source);

        dto.ExclusionType.Should().Be("DEBARMENT");
        dto.ExclusionProgram.Should().Be("RECIPROCAL");
        dto.ExcludingAgencyName.Should().Be("Dept of Defense");
        dto.ActivationDate.Should().Be(new DateOnly(2024, 1, 1));
        dto.TerminationDate.Should().Be(new DateOnly(2027, 1, 1));
        dto.AdditionalComments.Should().Be("Test comment");
    }

    [Fact]
    public void Map_SavedSearch_ToDto_ShouldMapCorrectly()
    {
        var source = new SavedSearch
        {
            SearchId = 5,
            UserId = 1,
            SearchName = "WOSB Opportunities",
            Description = "Search for WOSB set-asides",
            FilterCriteria = "{\"SetAsideCodes\":[\"WOSB\"]}",
            NotificationEnabled = "Y",
            IsActive = "Y",
            LastRunAt = new DateTime(2025, 6, 1, 10, 0, 0),
            LastNewResults = 3,
            CreatedAt = new DateTime(2025, 1, 1, 8, 0, 0)
        };

        var dto = _mapper.Map<SavedSearchDto>(source);

        dto.SearchId.Should().Be(5);
        dto.SearchName.Should().Be("WOSB Opportunities");
        dto.Description.Should().Be("Search for WOSB set-asides");
        dto.FilterCriteria.Should().Be("{\"SetAsideCodes\":[\"WOSB\"]}");
        dto.NotificationEnabled.Should().Be("Y");
        dto.IsActive.Should().Be("Y");
        dto.LastRunAt.Should().Be(new DateTime(2025, 6, 1, 10, 0, 0));
        dto.LastNewResults.Should().Be(3);
        dto.CreatedAt.Should().Be(new DateTime(2025, 1, 1, 8, 0, 0));
    }
}
