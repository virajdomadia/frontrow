import type { components } from "./api-types";

/**
 * The api's error envelope as an exception — shared by the server client (`api.ts`) and the
 * browser client (`client.ts`), so it imports nothing server-only.
 */
export type ApiErrorBody = components["schemas"]["ApiErrorBody"];

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public body: ApiErrorBody,
  ) {
    super(body.message);
  }
}

/** Only a body shaped like the api envelope is trusted; anything else keeps the HTTP status. */
export function errorFromResponse(status: number, statusText: string, raw: unknown) {
  const error = (raw as { error?: unknown } | undefined)?.error;
  if (isErrorBody(error)) return new ApiRequestError(status, error);
  return new ApiRequestError(status, { code: "internal", message: statusText || `HTTP ${status}` });
}

function isErrorBody(x: unknown): x is ApiErrorBody {
  return (
    typeof x === "object" &&
    x !== null &&
    typeof (x as ApiErrorBody).code === "string" &&
    typeof (x as ApiErrorBody).message === "string"
  );
}
