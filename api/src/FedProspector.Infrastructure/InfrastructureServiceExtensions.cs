using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Interceptors;
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
    /// <remarks>
    /// Connection string resolution order:
    /// 1. Environment variable: ConnectionStrings__DefaultConnection (or ConnectionStrings:DefaultConnection)
    /// 2. appsettings.{Environment}.json
    /// 3. appsettings.json (placeholder "SET_VIA_ENVIRONMENT" in production builds)
    ///
    /// Production connection strings should include SslMode=Required for encrypted connections.
    /// </remarks>
    public static IServiceCollection AddInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        // Environment variables are automatically merged by ASP.NET Core configuration.
        // Set ConnectionStrings__DefaultConnection as an env var for production deployments.
        var connectionString = configuration.GetConnectionString("DefaultConnection");

        if (string.IsNullOrEmpty(connectionString) || connectionString == "SET_VIA_ENVIRONMENT")
        {
            throw new InvalidOperationException(
                "Database connection string is not configured. " +
                "Set the 'ConnectionStrings__DefaultConnection' environment variable or configure it in appsettings.{Environment}.json.");
        }

        services.AddDbContext<FedProspectorDbContext>(options =>
            options.UseMySql(
                    connectionString,
                    ServerVersion.AutoDetect(connectionString),
                    mySqlOptions => mySqlOptions.EnableRetryOnFailure())
                .UseSnakeCaseNamingConvention()
                .AddInterceptors(new QueryHintInterceptor()));

        return services;
    }
}
