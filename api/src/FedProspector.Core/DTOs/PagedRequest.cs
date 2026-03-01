namespace FedProspector.Core.DTOs;

public class PagedRequest
{
    private int _page = 1;
    private int _pageSize = 25;

    public int Page
    {
        get => _page;
        set => _page = value < 1 ? 1 : value;
    }

    public int PageSize
    {
        get => _pageSize;
        set => _pageSize = value < 1 ? 1 : value > 100 ? 100 : value;
    }

    public string? SortBy { get; set; }
    public bool SortDescending { get; set; }
}
