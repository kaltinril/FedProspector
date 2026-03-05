/** Shared pagination request parameters matching C# PagedRequest */
export interface PagedRequest {
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDescending?: boolean;
}

/** Shared pagination response matching C# PagedResponse<T> */
export interface PagedResponse<T> {
  items: T[];
  page: number;
  pageSize: number;
  totalCount: number;
  totalPages: number;
  hasPreviousPage: boolean;
  hasNextPage: boolean;
}

/** Standard API error response matching C# ApiErrorResponse */
export interface ApiErrorResponse {
  status: number;
  title: string;
  detail?: string;
  errors?: Record<string, string[]>;
}
