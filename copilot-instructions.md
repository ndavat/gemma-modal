# GitHub Copilot Instructions

## Tech Stack
- Backend: .NET 8 / C# with clean architecture
- Frontend: Angular 17+
- Database: SQL Server with Entity Framework Core
- Cloud: Azure (App Service, Functions, Service Bus)
- APIs: RESTful with OpenAPI/Swagger documentation
- Testing: xUnit, Moq, FluentAssertions

## Code Style
- Use C# 12 features (primary constructors, collection expressions)
- Prefer `record` types for DTOs and value objects
- Use `Result<T>` pattern for error handling (ErrorOr library)
- Follow SOLID principles strictly
- Write XML doc comments for all public APIs
- Use `var` when type is obvious, explicit type otherwise

## Patterns
- Repository + Unit of Work pattern for data access
- CQRS with MediatR for business logic
- Serilog for structured logging
- FluentValidation for input validation
- Always include cancellationToken parameters in async methods

## Security
- Never log sensitive data (passwords, tokens, PII)
- Use Azure Key Vault references in config
- Validate all inputs, sanitize all outputs
- Follow OWASP top 10 guidelines

## Testing
- Write unit tests for all business logic
- Use xUnit with Theory/InlineData for parameterized tests
- Follow Arrange-Act-Assert pattern
- Target 80%+ code coverage for core domain logic
