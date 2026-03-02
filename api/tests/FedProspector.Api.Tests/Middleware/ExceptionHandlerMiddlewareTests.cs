using System.Net;
using System.Text.Json;
using FedProspector.Api.Middleware;
using FedProspector.Core.DTOs;
using FedProspector.Core.Exceptions;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Moq;

namespace FedProspector.Api.Tests.Middleware;

public class ExceptionHandlerMiddlewareTests
{
    private readonly Mock<ILogger<ExceptionHandlerMiddleware>> _loggerMock = new();

    private ExceptionHandlerMiddleware CreateMiddleware(RequestDelegate next)
    {
        return new ExceptionHandlerMiddleware(next, _loggerMock.Object);
    }

    private static DefaultHttpContext CreateHttpContext()
    {
        var context = new DefaultHttpContext();
        context.Response.Body = new MemoryStream();
        return context;
    }

    private static async Task<ApiErrorResponse?> ReadResponseBody(HttpContext context)
    {
        context.Response.Body.Seek(0, SeekOrigin.Begin);
        return await JsonSerializer.DeserializeAsync<ApiErrorResponse>(
            context.Response.Body,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
    }

    [Fact]
    public async Task InvokeAsync_NoException_CallsNextDelegate()
    {
        var wasCalled = false;
        var middleware = CreateMiddleware(_ => { wasCalled = true; return Task.CompletedTask; });
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        wasCalled.Should().BeTrue();
    }

    [Fact]
    public async Task InvokeAsync_KeyNotFoundException_Returns404()
    {
        var middleware = CreateMiddleware(_ => throw new KeyNotFoundException("Not found"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        context.Response.StatusCode.Should().Be(404);
    }

    [Fact]
    public async Task InvokeAsync_KeyNotFoundException_ReturnsGenericMessage()
    {
        var middleware = CreateMiddleware(_ => throw new KeyNotFoundException("User 42 not found"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        var body = await ReadResponseBody(context);
        body!.Message.Should().Be("The requested resource was not found.");
    }

    [Fact]
    public async Task InvokeAsync_InvalidOperationException_Returns400()
    {
        var middleware = CreateMiddleware(_ => throw new InvalidOperationException("Bad request"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        context.Response.StatusCode.Should().Be(400);
    }

    [Fact]
    public async Task InvokeAsync_InvalidOperationException_ReturnsGenericMessage()
    {
        var middleware = CreateMiddleware(_ => throw new InvalidOperationException("Sensitive details about operation"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        var body = await ReadResponseBody(context);
        body!.Message.Should().Be("The request could not be processed.");
    }

    [Fact]
    public async Task InvokeAsync_UnauthorizedAccessException_Returns403()
    {
        var middleware = CreateMiddleware(_ => throw new UnauthorizedAccessException("Forbidden"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        context.Response.StatusCode.Should().Be(403);
    }

    [Fact]
    public async Task InvokeAsync_UnauthorizedAccessException_ReturnsGenericMessage()
    {
        var middleware = CreateMiddleware(_ => throw new UnauthorizedAccessException("User 42 tried to access resource 99"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        var body = await ReadResponseBody(context);
        body!.Message.Should().Be("Access denied.");
    }

    [Fact]
    public async Task InvokeAsync_ConflictException_Returns409()
    {
        var middleware = CreateMiddleware(_ => throw new ConflictException("Conflict detected"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        context.Response.StatusCode.Should().Be(409);
    }

    [Fact]
    public async Task InvokeAsync_ConflictException_ReturnsGenericMessage()
    {
        var middleware = CreateMiddleware(_ => throw new ConflictException("Duplicate entry for email admin@test.com"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        var body = await ReadResponseBody(context);
        body!.Message.Should().Be("A conflict occurred with the current state of the resource.");
    }

    [Fact]
    public async Task InvokeAsync_UnhandledException_Returns500()
    {
        var middleware = CreateMiddleware(_ => throw new Exception("Something broke"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        context.Response.StatusCode.Should().Be(500);
    }

    [Fact]
    public async Task InvokeAsync_UnhandledException_ReturnsGenericMessage()
    {
        var middleware = CreateMiddleware(_ => throw new Exception("Sensitive details"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        var body = await ReadResponseBody(context);
        body!.Message.Should().Be("An internal server error occurred");
    }

    [Fact]
    public async Task InvokeAsync_AnyException_SetsJsonContentType()
    {
        var middleware = CreateMiddleware(_ => throw new Exception("test"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        context.Response.ContentType.Should().StartWith("application/json");
    }

    [Fact]
    public async Task InvokeAsync_AnyException_IncludesTraceId()
    {
        var middleware = CreateMiddleware(_ => throw new Exception("test"));
        var context = CreateHttpContext();
        context.TraceIdentifier = "test-trace-id";

        await middleware.InvokeAsync(context);

        var body = await ReadResponseBody(context);
        body!.TraceId.Should().Be("test-trace-id");
    }

    [Fact]
    public async Task InvokeAsync_AnyException_IncludesStatusCodeInBody()
    {
        var middleware = CreateMiddleware(_ => throw new KeyNotFoundException("test"));
        var context = CreateHttpContext();

        await middleware.InvokeAsync(context);

        var body = await ReadResponseBody(context);
        body!.StatusCode.Should().Be(404);
    }
}
