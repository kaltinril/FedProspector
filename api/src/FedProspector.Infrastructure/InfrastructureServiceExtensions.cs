using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace FedProspector.Infrastructure;

public static class InfrastructureServiceExtensions
{
    /// <summary>
    /// Registers the <see cref="FedProspectorDbContext"/> with MySQL (Pomelo)
    /// and snake_case naming conventions.
    /// </summary>
    public static IServiceCollection AddInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        var connectionString = configuration.GetConnectionString("DefaultConnection");

        services.AddDbContext<FedProspectorDbContext>(options =>
            options.UseMySql(
                    connectionString,
                    ServerVersion.AutoDetect(connectionString),
                    mySqlOptions => mySqlOptions.EnableRetryOnFailure())
                .UseSnakeCaseNamingConvention());

        return services;
    }
}
