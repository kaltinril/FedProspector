using System.Reflection;
using System.Text;
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
        Title = "Federal Contract Prospecting API",
        Version = "v1",
        Description = "REST API for federal contract opportunity discovery and capture management"
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

// 2. Swagger UI (all environments for now)
app.UseSwagger();
app.UseSwaggerUI(options =>
{
    options.SwaggerEndpoint("/swagger/v1/swagger.json", "FedProspector API v1");
    options.RoutePrefix = "swagger";
});

// 3. HTTPS redirect
app.UseHttpsRedirection();

// 4. CORS (before auth)
app.UseCors();

// 5. Authentication & Authorization
app.UseAuthentication();
app.UseAuthorization();

// 6. Map controllers
app.MapControllers();

app.Run();
