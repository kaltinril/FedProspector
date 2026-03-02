using System.Reflection;
using System.Text;
using System.Threading.RateLimiting;
using FedProspector.Api.Extensions;
using FedProspector.Api.Filters;
using FedProspector.Api.Middleware;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Options;
using FedProspector.Core.Validators;
using FedProspector.Infrastructure;
using FedProspector.Infrastructure.Services;
using FluentValidation;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.IdentityModel.Tokens;
using Microsoft.OpenApi;
using Serilog;
using AppCorsOptions = FedProspector.Core.Options.CorsOptions;

var builder = WebApplication.CreateBuilder(args);

// --- Serilog ---
builder.Host.UseSerilog((context, loggerConfig) =>
    loggerConfig.ReadFrom.Configuration(context.Configuration));

// --- Strongly-typed options ---
builder.Services.Configure<JwtOptions>(builder.Configuration.GetSection(JwtOptions.SectionName));
builder.Services.Configure<AppCorsOptions>(builder.Configuration.GetSection(AppCorsOptions.SectionName));

// --- Database ---
builder.Services.AddInfrastructure(builder.Configuration);

// --- Authentication (JWT Bearer) ---
var jwtOptions = builder.Configuration.GetSection(JwtOptions.SectionName).Get<JwtOptions>()!;
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = jwtOptions.Issuer,
            ValidAudience = jwtOptions.Audience,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtOptions.SecretKey))
        };
    });
builder.Services.AddAuthorization();

// --- Application services ---
builder.Services.AddScoped<IAuthService, AuthService>();
builder.Services.AddScoped<IOpportunityService, OpportunityService>();
builder.Services.AddScoped<IAwardService, AwardService>();
builder.Services.AddScoped<IEntityService, EntityService>();
builder.Services.AddScoped<ISubawardService, SubawardService>();
builder.Services.AddScoped<IDashboardService, DashboardService>();
builder.Services.AddScoped<IAdminService, AdminService>();
builder.Services.AddScoped<ISavedSearchService, SavedSearchService>();
builder.Services.AddScoped<IActivityLogService, ActivityLogService>();
builder.Services.AddScoped<IGoNoGoScoringService, GoNoGoScoringService>();
builder.Services.AddScoped<IProspectService, ProspectService>();
builder.Services.AddScoped<IProposalService, ProposalService>();
builder.Services.AddScoped<INotificationService, NotificationService>();

// --- Core services (AutoMapper, Repositories) ---
builder.Services.AddCoreServices();

// --- FluentValidation ---
builder.Services.AddValidatorsFromAssemblyContaining<LoginRequestValidator>();

// --- CORS ---
var corsOptions = builder.Configuration.GetSection(AppCorsOptions.SectionName).Get<AppCorsOptions>();
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.WithOrigins(corsOptions?.AllowedOrigins ?? ["http://localhost:3000"])
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials();
    });
});

// --- Rate Limiting ---
builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

    // Auth endpoints: 10/min per IP
    options.AddPolicy("auth", context =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: context.Connection.RemoteIpAddress?.ToString() ?? "unknown",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 10,
                Window = TimeSpan.FromMinutes(1),
                QueueLimit = 0
            }));

    // Search/read endpoints: 60/min per user
    options.AddPolicy("search", context =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: context.User?.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value
                          ?? context.User?.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value
                          ?? context.Connection.RemoteIpAddress?.ToString()
                          ?? "unknown",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 60,
                Window = TimeSpan.FromMinutes(1),
                QueueLimit = 0
            }));

    // Write endpoints: 30/min per user
    options.AddPolicy("write", context =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: context.User?.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value
                          ?? context.User?.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value
                          ?? context.Connection.RemoteIpAddress?.ToString()
                          ?? "unknown",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 30,
                Window = TimeSpan.FromMinutes(1),
                QueueLimit = 0
            }));

    // Admin endpoints: 30/min per user
    options.AddPolicy("admin", context =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: context.User?.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value
                          ?? context.User?.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value
                          ?? context.Connection.RemoteIpAddress?.ToString()
                          ?? "unknown",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 30,
                Window = TimeSpan.FromMinutes(1),
                QueueLimit = 0
            }));

    options.OnRejected = async (context, cancellationToken) =>
    {
        context.HttpContext.Response.ContentType = "application/json";
        var response = new { statusCode = 429, message = "Too many requests. Please try again later." };
        await context.HttpContext.Response.WriteAsJsonAsync(response, cancellationToken);
    };
});

// --- Controllers + global filters ---
builder.Services.AddControllers(options =>
{
    options.Filters.Add<FluentValidationFilter>();
});

// --- Swagger / OpenAPI ---
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "FedProspector API",
        Version = "v1",
        Description = "Federal contract prospecting system API — search opportunities, manage prospects, track proposals",
        Contact = new OpenApiContact
        {
            Name = "FedProspector",
        }
    });

    // JWT auth in Swagger UI
    options.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
    {
        Description = "JWT Authorization header. Enter 'Bearer {token}'",
        Name = "Authorization",
        In = ParameterLocation.Header,
        Type = SecuritySchemeType.ApiKey,
        Scheme = "Bearer"
    });

    options.AddSecurityRequirement(_ => new OpenApiSecurityRequirement
    {
        {
            new OpenApiSecuritySchemeReference("Bearer"),
            new List<string>()
        }
    });

    // Include XML comments if available
    var xmlFile = $"{Assembly.GetExecutingAssembly().GetName().Name}.xml";
    var xmlPath = Path.Combine(AppContext.BaseDirectory, xmlFile);
    if (File.Exists(xmlPath))
        options.IncludeXmlComments(xmlPath);
});

var app = builder.Build();

// --- Middleware pipeline (order matters) ---

// 1. Global exception handler (first, catches everything)
app.UseMiddleware<ExceptionHandlerMiddleware>();

// 2. Security headers (early, applies to all responses)
app.UseMiddleware<SecurityHeadersMiddleware>();

// 3. Swagger UI (all environments for now)
app.UseSwagger();
app.UseSwaggerUI(options =>
{
    options.SwaggerEndpoint("/swagger/v1/swagger.json", "FedProspector API v1");
    options.RoutePrefix = "swagger";
});

// 4. HTTPS redirect
app.UseHttpsRedirection();

// 5. CORS (before auth)
app.UseCors();

// 6. Authentication & Authorization
app.UseAuthentication();
app.UseAuthorization();

// 7. Rate limiting (after auth, before controllers)
app.UseRateLimiter();

// 8. Map controllers
app.MapControllers();

app.Run();
