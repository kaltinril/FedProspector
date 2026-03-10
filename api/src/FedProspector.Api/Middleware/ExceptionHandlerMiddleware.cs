using FedProspector.Core.DTOs;
using FedProspector.Core.Exceptions;
using Microsoft.EntityFrameworkCore;

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
        catch (OperationCanceledException) when (context.RequestAborted.IsCancellationRequested)
        {
            // Client disconnected — not an error
            context.Response.StatusCode = 499;
            return;
        }
        catch (Exception ex)
        {
            var (statusCode, message) = ex switch
            {
                KeyNotFoundException => (404, "The requested resource was not found."),
                ArgumentException => (400, "Invalid argument provided."),
                InvalidOperationException => (400, "The request could not be processed."),
                UnauthorizedAccessException => (403, "Access denied."),
                ConflictException => (409, "A conflict occurred with the current state of the resource."),
                DbUpdateConcurrencyException => (409, "A concurrency conflict occurred. Please retry."),
                DbUpdateException dbEx when dbEx.InnerException?.Message.Contains("Duplicate entry", StringComparison.OrdinalIgnoreCase) == true
                    => (409, "A conflict occurred due to a duplicate entry."),
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
