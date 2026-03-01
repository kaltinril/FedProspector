using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Repositories;

namespace FedProspector.Api.Extensions;

public static class CoreServiceExtensions
{
    /// <summary>
    /// Registers AutoMapper (assembly scanning) and generic repository interfaces.
    /// </summary>
    public static IServiceCollection AddCoreServices(this IServiceCollection services)
    {
        // AutoMapper — register profile from FedProspector.Core
        services.AddAutoMapper(cfg => cfg.AddProfile<FedProspector.Core.Mapping.MappingProfile>());

        // Generic repositories — open generic registration
        services.AddScoped(typeof(IReadOnlyRepository<>), typeof(ReadOnlyRepository<>));
        services.AddScoped(typeof(IRepository<>), typeof(Repository<>));

        return services;
    }
}
