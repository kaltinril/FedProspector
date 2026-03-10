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

// --- Memory Cache (for session validation) ---
builder.Services.AddMemoryCache();

// --- Authentication (JWT Bearer with cookie support) ---
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
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtOptions.SecretKey)),
            ClockSkew = TimeSpan.Zero
        };

        options.Events = new JwtBearerEvents
        {
            // Read token from cookie if no Authorization header is present
            OnMessageReceived = context =>
            {
                var authHeader = context.Request.Headers.Authorization.ToString();
                if (string.IsNullOrEmpty(authHeader) || !authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
                {
                    var accessToken = context.Request.Cookies["access_token"];
                    if (!string.IsNullOrEmpty(accessToken))
                    {
                        context.Token = accessToken;
                    }
                }
                return Task.CompletedTask;
            },

            // Validate session exists and is not revoked on every authenticated request
            OnTokenValidated = async context =>
            {
                var authService = context.HttpContext.RequestServices.GetRequiredService<IAuthService>();
                var sub = context.Principal?.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value
                       ?? context.Principal?.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;

                if (sub == null || !int.TryParse(sub, out var userId))
                {
                    context.Fail("Invalid token claims.");
                    return;
                }

                // Get the raw token to compute hash
                var rawToken = context.Request.Headers.Authorization.ToString();
                string? token = null;
                if (!string.IsNullOrEmpty(rawToken) && rawToken.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
                {
                    token = rawToken["Bearer ".Length..].Trim();
                }
                else
                {
                    token = context.Request.Cookies["access_token"];
                }

                if (string.IsNullOrEmpty(token))
                {
                    context.Fail("Token not found.");
                    return;
                }

                var tokenHash = ComputeSha256Hash(token);
                var isValid = await authService.ValidateSessionAsync(userId, tokenHash);

                if (!isValid)
                {
                    context.Fail("Session has been revoked.");
                }
            }
        };
    });

// --- Authorization with OrgAdmin and SystemAdmin policies ---
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("OrgAdmin", policy =>
        policy.RequireAssertion(context =>
        {
            var orgRole = context.User.FindFirst("org_role")?.Value;
            return orgRole is "owner" or "admin";
        }));

    options.AddPolicy("SystemAdmin", policy =>
        policy.RequireClaim("is_system_admin", "true"));

    options.AddPolicy("AdminAccess", policy =>
        policy.RequireAssertion(context =>
        {
            // Allow org admins (role claim) OR system admins (is_system_admin claim)
            var isOrgAdmin = context.User.IsInRole("admin");
            var isSystemAdmin = context.User.FindFirst("is_system_admin")?.Value == "true";
            return isOrgAdmin || isSystemAdmin;
        }));
});

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
builder.Services.AddScoped<IOrganizationService, OrganizationService>();
builder.Services.AddScoped<ICompanyProfileService, CompanyProfileService>();
builder.Services.AddScoped<IPWinService, PWinService>();
builder.Services.AddScoped<IExpiringContractService, ExpiringContractService>();
builder.Services.AddScoped<IRecommendedOpportunityService, RecommendedOpportunityService>();
builder.Services.AddScoped<IMarketIntelService, MarketIntelService>();
builder.Services.AddScoped<IQualificationService, QualificationService>();

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
        policy.WithOrigins(corsOptions?.AllowedOrigins ?? ["http://localhost:5173"])
              .WithHeaders("Authorization", "Content-Type", "Accept", "X-XSRF-TOKEN")
              .WithMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
              .AllowCredentials();
    });
});

// --- Rate Limiting ---
const int rateLimitRetryAfterSeconds = 60;
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

    // Global login rate limit: 100 total login attempts per minute (all IPs combined)
    options.AddPolicy("login_global", _ =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: "global_login",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 100,
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
        context.HttpContext.Response.Headers["Retry-After"] = rateLimitRetryAfterSeconds.ToString();
        context.HttpContext.Response.ContentType = "application/json";
        var response = new
        {
            statusCode = 429,
            message = "Too many requests. Please try again later.",
            retryAfterSeconds = rateLimitRetryAfterSeconds
        };
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

// --- Startup guards ---
if (!app.Environment.IsDevelopment())
{
    var jwtSecret = app.Configuration["Jwt:SecretKey"];
    if (string.IsNullOrEmpty(jwtSecret) || jwtSecret.Contains("CHANGE_ME") || jwtSecret.Length < 32)
        throw new InvalidOperationException(
            "JWT secret key must be configured for non-development environments. " +
            "Set Jwt:SecretKey to a secure value of at least 32 characters.");
}

// --- Middleware pipeline (order matters) ---

// 1. Global exception handler (first, catches everything)
app.UseMiddleware<ExceptionHandlerMiddleware>();

// 2. Security headers (early, applies to all responses)
app.UseMiddleware<SecurityHeadersMiddleware>();

// 3. Swagger UI (development only)
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/swagger/v1/swagger.json", "FedProspector API v1");
        options.RoutePrefix = "swagger";
    });
}

// 4. HTTPS redirect (skip in development — breaks Vite dev proxy targeting HTTP)
if (!app.Environment.IsDevelopment())
{
    app.UseHttpsRedirection();
}

// 5. CORS (before auth)
app.UseCors();

// 6. Authentication & Authorization
app.UseAuthentication();
app.UseAuthorization();

// 7. CSRF protection (after auth, before controllers)
app.UseMiddleware<CsrfMiddleware>();

// 8. Force password change enforcement (after auth, before controllers)
app.UseMiddleware<ForcePasswordChangeMiddleware>();

// 9. Rate limiting (after auth, before controllers)
app.UseRateLimiter();

// 10. Map controllers
app.MapControllers();

app.Run();

// Local helper for SHA-256 hashing used in JWT events
static string ComputeSha256Hash(string input)
{
    var bytes = System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(input));
    return Convert.ToHexStringLower(bytes);
}
