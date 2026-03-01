using System.Linq.Expressions;
using FedProspector.Core.DTOs;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;

namespace FedProspector.Infrastructure.Repositories;

public class Repository<T> : IRepository<T> where T : class
{
    protected readonly FedProspectorDbContext Context;
    protected readonly DbSet<T> DbSet;

    public Repository(FedProspectorDbContext context)
    {
        Context = context;
        DbSet = context.Set<T>();
    }

    public virtual async Task<T?> GetByIdAsync(object id)
    {
        return await DbSet.FindAsync(id);
    }

    public virtual async Task<IEnumerable<T>> GetAllAsync()
    {
        return await DbSet.ToListAsync();
    }

    public virtual async Task<PagedResponse<T>> GetPagedAsync(
        PagedRequest request,
        Expression<Func<T, bool>>? filter = null)
    {
        IQueryable<T> query = DbSet;

        if (filter != null)
        {
            query = query.Where(filter);
        }

        var totalCount = await query.CountAsync();

        query = ApplyOrdering(query, request);

        var items = await query
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToListAsync();

        return new PagedResponse<T>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public virtual IQueryable<T> Query()
    {
        return DbSet;
    }

    public virtual async Task<T> AddAsync(T entity)
    {
        var entry = await DbSet.AddAsync(entity);
        return entry.Entity;
    }

    public virtual Task UpdateAsync(T entity)
    {
        DbSet.Update(entity);
        return Task.CompletedTask;
    }

    public virtual Task DeleteAsync(T entity)
    {
        DbSet.Remove(entity);
        return Task.CompletedTask;
    }

    public virtual async Task SaveChangesAsync()
    {
        await Context.SaveChangesAsync();
    }

    /// <summary>
    /// Applies ordering to the query. If SortBy is specified and the property exists
    /// on the entity, orders by that property. Otherwise falls back to the entity's
    /// primary key in descending order.
    /// </summary>
    private IQueryable<T> ApplyOrdering(IQueryable<T> query, PagedRequest request)
    {
        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            var entityType = Context.Model.FindEntityType(typeof(T));
            var property = entityType?.FindProperty(request.SortBy);

            if (property != null)
            {
                var parameter = Expression.Parameter(typeof(T), "e");
                var propertyAccess = Expression.Property(parameter, request.SortBy);
                var converted = Expression.Convert(propertyAccess, typeof(object));
                var lambda = Expression.Lambda<Func<T, object>>(converted, parameter);

                return request.SortDescending
                    ? query.OrderByDescending(lambda)
                    : query.OrderBy(lambda);
            }
        }

        return ApplyDefaultOrdering(query);
    }

    /// <summary>
    /// Orders by the entity's primary key in descending order.
    /// If no primary key is found, returns the query unordered.
    /// </summary>
    private IQueryable<T> ApplyDefaultOrdering(IQueryable<T> query)
    {
        var entityType = Context.Model.FindEntityType(typeof(T));
        var primaryKey = entityType?.FindPrimaryKey();

        if (primaryKey == null || primaryKey.Properties.Count == 0)
        {
            return query;
        }

        var pkPropertyName = primaryKey.Properties[0].Name;
        var parameter = Expression.Parameter(typeof(T), "e");
        var propertyAccess = Expression.Property(parameter, pkPropertyName);
        var converted = Expression.Convert(propertyAccess, typeof(object));
        var lambda = Expression.Lambda<Func<T, object>>(converted, parameter);

        return query.OrderByDescending(lambda);
    }
}
