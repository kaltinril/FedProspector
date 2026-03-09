# Cross-Layer Type Mapping

## Type Equivalence Table

| Logical Type | Python Parser | MySQL Column | C# Property | TypeScript | Display Format |
|-------------|--------------|-------------|-------------|-----------|---------------|
| **string** | `str(raw.get("field"))` | `VARCHAR(n)` | `string?` | `string \| null` | Direct display |
| **text** | `str(raw.get("field"))` | `TEXT` or `LONGTEXT` | `string?` | `string \| null` | May need truncation |
| **decimal** | `parse_decimal(raw.get("field"))` | `DECIMAL(15,2)` | `decimal?` `[Column(TypeName = "decimal(15,2)")]` | `number \| null` | `formatCurrency()` |
| **int** | `int(raw.get("field"))` | `INT` | `int?` | `number \| null` | Direct display |
| **date** | `parse_date(raw.get("field"))` | `DATE` | `DateOnly?` | `string \| null` | `formatDate()` |
| **datetime** | `parse_datetime(raw.get("field"))` | `DATETIME` | `DateTime?` | `string \| null` | `formatDateTime()` |
| **bool** | `"Y" if raw.get("field") == "Yes" else "N"` | `CHAR(1)` | `string?` or `bool?` | `boolean \| null` or `string \| null` | Yes/No or Y/N |
| **json** | `json.dumps(raw.get("field"))` | `JSON` | `string?` | `string \| null` or typed | Parse in service layer |
| **hash** | `change_detector.compute_hash(...)` | `CHAR(64)` | `string?` | N/A | Internal only |

## C# Attribute Cheatsheet

| MySQL Type | C# Attribute |
|-----------|-------------|
| `DECIMAL(15,2)` | `[Column(TypeName = "decimal(15,2)")]` |
| `VARCHAR(100)` | `[MaxLength(100)]` |
| Primary key | `[Key]` |
| Required | No `?` suffix (non-nullable) |

## Naming Convention Transforms

| Source (snake_case) | MySQL | C# (PascalCase) | TypeScript (camelCase) | Display (Title Case) |
|--------------------|-------|-----------------|----------------------|---------------------|
| `estimated_value` | `estimated_value` | `EstimatedValue` | `estimatedValue` | `Estimated Value` |
| `notice_id` | `notice_id` | `NoticeId` | `noticeId` | `Notice ID` |
| `posted_date` | `posted_date` | `PostedDate` | `postedDate` | `Posted Date` |
| `is_active` | `is_active` | `IsActive` | `isActive` | `Active` |

## Common Mistakes to Avoid

1. **Decimal as float**: Never use Python `float` or TypeScript implicit float parsing for monetary values. Use `parse_decimal()` -> `DECIMAL(15,2)` -> `decimal?` -> `number`.
2. **Date as string**: Always use `parse_date()` in Python, `DATE`/`DateOnly` in C#. Don't store dates as VARCHAR.
3. **Missing hash field**: If the field represents a business-meaningful change, it MUST be in `_HASH_FIELDS`. Missing it = false "unchanged" detection.
4. **C# nullable mismatch**: New fields should be nullable (`?` suffix) unless there's a NOT NULL constraint in DDL.
5. **TypeScript casing**: C# `EstimatedValue` auto-serializes to `estimatedValue` in JSON. TypeScript must use camelCase.
