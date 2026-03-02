using FluentAssertions;
using FedProspector.Core.DTOs;

namespace FedProspector.Core.Tests.DTOs;

public class PagedResponseTests
{
    [Fact]
    public void TotalPages_ExactDivision_ShouldReturnCorrectCount()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 100,
            PageSize = 25,
            Page = 1
        };

        response.TotalPages.Should().Be(4);
    }

    [Fact]
    public void TotalPages_WithRemainder_ShouldRoundUp()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 101,
            PageSize = 25,
            Page = 1
        };

        response.TotalPages.Should().Be(5);
    }

    [Fact]
    public void TotalPages_ZeroTotalCount_ShouldReturnZero()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 0,
            PageSize = 25,
            Page = 1
        };

        response.TotalPages.Should().Be(0);
    }

    [Fact]
    public void TotalPages_SingleItem_ShouldReturnOne()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 1,
            PageSize = 25,
            Page = 1
        };

        response.TotalPages.Should().Be(1);
    }

    [Fact]
    public void TotalPages_TotalCountEqualsPageSize_ShouldReturnOne()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 25,
            PageSize = 25,
            Page = 1
        };

        response.TotalPages.Should().Be(1);
    }

    [Fact]
    public void HasPreviousPage_FirstPage_ShouldBeFalse()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 100,
            PageSize = 25,
            Page = 1
        };

        response.HasPreviousPage.Should().BeFalse();
    }

    [Fact]
    public void HasPreviousPage_SecondPage_ShouldBeTrue()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 100,
            PageSize = 25,
            Page = 2
        };

        response.HasPreviousPage.Should().BeTrue();
    }

    [Fact]
    public void HasNextPage_LastPage_ShouldBeFalse()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 100,
            PageSize = 25,
            Page = 4
        };

        response.HasNextPage.Should().BeFalse();
    }

    [Fact]
    public void HasNextPage_FirstPageOfMany_ShouldBeTrue()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 100,
            PageSize = 25,
            Page = 1
        };

        response.HasNextPage.Should().BeTrue();
    }

    [Fact]
    public void HasNextPage_OnlyOnePage_ShouldBeFalse()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 10,
            PageSize = 25,
            Page = 1
        };

        response.HasNextPage.Should().BeFalse();
    }

    [Fact]
    public void HasPreviousPage_OnlyOnePage_ShouldBeFalse()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 10,
            PageSize = 25,
            Page = 1
        };

        response.HasPreviousPage.Should().BeFalse();
    }

    [Fact]
    public void HasNextPage_EmptyResults_ShouldBeFalse()
    {
        var response = new PagedResponse<string>
        {
            TotalCount = 0,
            PageSize = 25,
            Page = 1
        };

        response.HasNextPage.Should().BeFalse();
    }

    [Fact]
    public void Items_DefaultValue_ShouldBeEmptyCollection()
    {
        var response = new PagedResponse<string>();

        response.Items.Should().BeEmpty();
    }

    [Theory]
    [InlineData(50, 10, 5)]
    [InlineData(51, 10, 6)]
    [InlineData(1, 10, 1)]
    [InlineData(10, 10, 1)]
    [InlineData(11, 10, 2)]
    [InlineData(0, 10, 0)]
    public void TotalPages_VariousCombinations_ShouldCalculateCorrectly(
        int totalCount, int pageSize, int expectedTotalPages)
    {
        var response = new PagedResponse<int>
        {
            TotalCount = totalCount,
            PageSize = pageSize,
            Page = 1
        };

        response.TotalPages.Should().Be(expectedTotalPages);
    }

    [Theory]
    [InlineData(1, false, true)]
    [InlineData(2, true, true)]
    [InlineData(3, true, true)]
    [InlineData(4, true, false)]
    public void Pagination_MiddlePages_ShouldReportCorrectNavigability(
        int page, bool expectedHasPrevious, bool expectedHasNext)
    {
        var response = new PagedResponse<int>
        {
            TotalCount = 100,
            PageSize = 25,
            Page = page
        };

        response.HasPreviousPage.Should().Be(expectedHasPrevious);
        response.HasNextPage.Should().Be(expectedHasNext);
    }
}
