namespace FedProspector.Core.Interfaces;

public interface IRepository<T> : IReadOnlyRepository<T> where T : class
{
    Task<T> AddAsync(T entity);
    Task UpdateAsync(T entity);
    Task DeleteAsync(T entity);
    Task SaveChangesAsync();
}
