using System.Security.Cryptography;

namespace FedProspector.Api.Middleware;

/// <summary>
/// CSRF double-submit cookie protection.
/// For POST/PATCH/DELETE requests using cookie auth (not Bearer header),
/// validates that the X-XSRF-TOKEN header matches the XSRF-TOKEN cookie.
/// GET requests and requests with Authorization: Bearer header skip CSRF validation.
/// </summary>
public class CsrfMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<CsrfMiddleware> _logger;

    private static readonly HashSet<string> MutatingMethods = new(StringComparer.OrdinalIgnoreCase)
    {
        "POST", "PUT", "PATCH", "DELETE"
    };

    // Auth endpoints exempt from CSRF — these establish sessions before a token exists
    private static readonly HashSet<string> CsrfExemptPaths = new(StringComparer.OrdinalIgnoreCase)
    {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh"
    };

    public CsrfMiddleware(RequestDelegate next, ILogger<CsrfMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var method = context.Request.Method;

        // Only validate CSRF for mutating methods
        if (MutatingMethods.Contains(method))
        {
            // Skip CSRF for unauthenticated auth endpoints
            if (CsrfExemptPaths.Contains(context.Request.Path.Value ?? ""))
            {
                await _next(context);
                return;
            }
            var authHeader = context.Request.Headers.Authorization.ToString();
            var hasBearerToken = !string.IsNullOrEmpty(authHeader) &&
                                 authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase);

            // Skip CSRF if using Bearer auth (non-browser clients)
            if (!hasBearerToken)
            {
                // Check if using cookie auth
                var hasAccessTokenCookie = context.Request.Cookies.ContainsKey("access_token");

                if (hasAccessTokenCookie)
                {
                    var cookieToken = context.Request.Cookies["XSRF-TOKEN"];
                    var headerToken = context.Request.Headers["X-XSRF-TOKEN"].ToString();

                    if (string.IsNullOrEmpty(cookieToken) ||
                        string.IsNullOrEmpty(headerToken) ||
                        !string.Equals(cookieToken, headerToken, StringComparison.Ordinal))
                    {
                        _logger.LogWarning("CSRF validation failed for {Method} {Path}",
                            method, context.Request.Path);

                        context.Response.StatusCode = 403;
                        context.Response.ContentType = "application/json";
                        await context.Response.WriteAsJsonAsync(new
                        {
                            statusCode = 403,
                            message = "CSRF validation failed."
                        });
                        return;
                    }
                }
            }
        }

        await _next(context);
    }

    /// <summary>
    /// Generate a cryptographically random CSRF token value.
    /// </summary>
    public static string GenerateCsrfToken()
    {
        var bytes = RandomNumberGenerator.GetBytes(32);
        return Convert.ToBase64String(bytes);
    }
}
