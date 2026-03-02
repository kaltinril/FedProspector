using FedProspector.Core.DTOs;
using FedProspector.Core.Exceptions;

namespace FedProspector.Api.Middleware;

public class ExceptionHandlerMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<ExceptionHandlerMiddleware> _logger;

    public ExceptionHandlerMiddleware(RequestDelegate next, ILogger<ExceptionHandlerMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (Exception ex)
        {
            var (statusCode, message) = ex switch
            {
                KeyNotFoundException => (404, "The requested resource was not found."),
                InvalidOperationException => (400, "The request could not be processed."),
                UnauthorizedAccessException => (403, "Access denied."),
                ConflictException => (409, "A conflict occurred with the current state of the resource."),
                _ => (500, "An internal server error occurred")
            };

            if (statusCode == 500)
            {
                _logger.LogError(ex, "Unhandled exception for {Method} {Path}",
                    context.Request.Method, context.Request.Path);
            }
            else
            {
                _logger.LogWarning(ex, "Handled exception ({StatusCode}) for {Method} {Path}",
                    statusCode, context.Request.Method, context.Request.Path);
            }

            context.Response.StatusCode = statusCode;
            context.Response.ContentType = "application/json";

            var response = new ApiErrorResponse
            {
                StatusCode = statusCode,
                Message = message,
                TraceId = context.TraceIdentifier
            };

            await context.Response.WriteAsJsonAsync(response);
        }
    }
}
