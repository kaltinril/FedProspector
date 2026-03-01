using System.Linq.Expressions;
using FedProspector.Core.DTOs;

namespace FedProspector.Core.Interfaces;

public interface IReadOnlyRepository<T> where T : class
{
    Task<T?> GetByIdAsync(object id);
    Task<IEnumerable<T>> GetAllAsync();
    Task<PagedResponse<T>> GetPagedAsync(PagedRequest request, Expression<Func<T, bool>>? filter = null);
    IQueryable<T> Query();
}
