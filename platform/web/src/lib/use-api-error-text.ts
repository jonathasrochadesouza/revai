/**
 * Resolve thrown values into localized, human error sentences.
 *
 * The single place components turn an unknown `catch (error)` into text:
 * `ApiError` instances carrying the backend's `{ error_key, params }`
 * contract resolve through the error catalog in the active locale; anything
 * else keeps its message or falls back to a generic sentence.
 */

"use client";

import { useCallback } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import { resolveApiError } from "@/lib/errors";

type ErrorText = (error: unknown) => string;

export function useApiErrorText(): ErrorText {
  const { locale } = useUiText();
  return useCallback((error: unknown) => resolveApiError(error, locale), [locale]);
}
