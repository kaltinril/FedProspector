# Tech Stack Reference

Last updated: 2026-03-21

---

## Runtime Environments

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.14.3 | Data gathering, ETL pipeline, CLI |
| .NET | 10.0 | ASP.NET Core Web API backend |
| Node.js | 22.22.1 | Frontend build tooling (NVM for Windows 1.2.2) |
| npm | 10.9.4 | Package manager |
| MySQL | 8.4.8 LTS | InnoDB, utf8mb4, standalone at `E:\mysql` |

---

## Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| requests | 2.32.5 | HTTP client for vendor APIs |
| mysql-connector-python | 9.6.0 | MySQL database driver |
| python-dotenv | 1.2.2 | .env config loading |
| lxml | 6.0.2 | XML parsing (SAM.gov extracts) |
| apscheduler | 3.11.2 | Scheduled ETL jobs |
| click | 8.3.1 | CLI framework |
| tqdm | 4.67.3 | Progress bars |
| ijson | 3.5.0 | Streaming JSON parser |
| bcrypt | 5.0.0 | Password hashing |
| pytest | 9.0.2 | Test framework |
| pymupdf | 1.27.2.2 | PDF text extraction (structure-aware) |
| python-docx | 1.2.0 | Word .docx text extraction |
| openpyxl | 3.1.5 | Excel .xlsx text extraction |
| python-pptx | 1.0.2 | PowerPoint .pptx text extraction |
| xlrd | 2.0.2 | Legacy Excel .xls text extraction |
| striprtf | 0.0.29 | Rich Text Format extraction |
| odfpy | 1.4.1 | OpenDocument .odt text extraction |
| olefile | 0.47 | OLE2 file inspection (IRM/DRM detection) |

### System Dependencies

| Tool | Version | Purpose |
|------|---------|---------|
| LibreOffice | 25.8.5.2 | Legacy .doc → .docx conversion (headless mode) |

---

## Frontend (UI)

### Core

| Package | Version | Purpose |
|---------|---------|---------|
| vite | 8.0.1 | Build tool + dev server |
| react | 19.2.4 | UI framework |
| react-dom | 19.2.4 | React DOM renderer |
| typescript | 5.9.3 | Type system |

### UI Framework & Components

| Package | Version | Purpose |
|---------|---------|---------|
| @mui/material | 7.3.9 | Component library |
| @mui/icons-material | 7.3.9 | Icon set |
| @mui/x-data-grid | 8.27.5 | Data tables |
| @mui/x-charts | 8.27.5 | Charts |
| @emotion/react | 11.14.0 | CSS-in-JS (MUI styling) |
| @emotion/styled | 11.14.1 | Styled components |

### State & Data

| Package | Version | Purpose |
|---------|---------|---------|
| @tanstack/react-query | 5.91.2 | Server state management |
| @tanstack/react-query-devtools | 5.91.3 | Query debugging |
| axios | 1.13.6 | HTTP client |
| react-hook-form | 7.71.2 | Form state |
| @hookform/resolvers | 5.2.2 | Form validation bridge |
| zod | 4.3.6 | Schema validation |

### Routing & UX

| Package | Version | Purpose |
|---------|---------|---------|
| react-router-dom | 7.13.1 | Client-side routing |
| notistack | 3.0.2 | Snackbar notifications |
| react-error-boundary | 6.1.1 | Error boundary wrapper |
| dompurify | 3.3.3 | HTML sanitization |
| @dnd-kit/core | 6.3.1 | Drag and drop |
| @dnd-kit/sortable | 10.0.0 | Sortable lists |
| date-fns | 4.1.0 | Date utilities |

### Dev Tooling

| Package | Version | Purpose |
|---------|---------|---------|
| @vitejs/plugin-react | 6.0.1 | Vite React support |
| eslint | 9.39.4 | Linting |
| typescript-eslint | 8.57.1 | TS lint rules |
| eslint-plugin-react-hooks | 7.0.1 | Hooks lint rules |
| eslint-plugin-jsx-a11y | 6.10.2 | Accessibility lint |
| eslint-plugin-react-refresh | 0.5.2 | Fast refresh lint |
| prettier | 3.8.1 | Code formatting |
| rollup-plugin-visualizer | 7.0.1 | Bundle analysis |

---

## Backend API (.NET)

### Application

| Package | Version | Purpose |
|---------|---------|---------|
| Microsoft.AspNetCore.Authentication.JwtBearer | 10.0.5 | JWT auth |
| FluentValidation.DependencyInjectionExtensions | 12.1.1 | Request validation + DI |
| FluentValidation | 12.1.1 | Validation rules |
| AutoMapper | 16.1.1 | Object mapping |
| Serilog.AspNetCore | 10.0.0 | Structured logging |
| Serilog.Sinks.File | 7.0.0 | File log sink |
| Swashbuckle.AspNetCore | 10.1.5 | Swagger/OpenAPI |
| Microsoft.OpenApi | 3.4.0 | OpenAPI spec |

### Data Access

| Package | Version | Purpose |
|---------|---------|---------|
| Pomelo.EntityFrameworkCore.MySql | 9.0.0 | EF Core MySQL provider |
| Microsoft.EntityFrameworkCore.Design | 9.0.7 | EF Core migrations tooling |
| EFCore.NamingConventions | 9.0.0 | snake_case column naming |
| BCrypt.Net-Next | 4.1.0 | Password hashing |

### Testing

| Package | Version | Purpose |
|---------|---------|---------|
| xunit | 2.9.3 | Test framework |
| xunit.runner.visualstudio | 3.1.5 | VS test runner |
| Microsoft.NET.Test.Sdk | 18.3.0 | Test host |
| Moq | 4.20.72 | Mocking |
| FluentAssertions | 8.9.0 | Assertion library |
| Microsoft.AspNetCore.Mvc.Testing | 10.0.5 | Integration test host |
| Microsoft.EntityFrameworkCore.InMemory | 9.0.7 | In-memory DB for tests |
| coverlet.collector | 8.0.1 | Code coverage |
