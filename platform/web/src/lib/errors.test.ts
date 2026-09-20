import { describe, expect, it } from "vitest";

import {
  ERROR_CATALOG,
  resolveApiError,
  resolveErrorDetail,
  resolveErrorDetails,
} from "@/lib/errors";
import type { ApiErrorDetail } from "@/lib/errors";

describe("error catalog", () => {
  it("covers every domain the backend can raise", () => {
    // The domains from the error-contract design; a key outside these domains
    // needs an explicit catalog decision, which this check forces.
    const domains = new Set(Object.keys(ERROR_CATALOG).map((key) => key.split(".")[0]));
    expect([...domains].sort()).toEqual(
      [
        "ai_pipeline",
        "budget",
        "credential",
        "export",
        "fix",
        "folder_picker",
        "git",
        "internal",
        "project",
        "prompt_scenario",
        "provider",
        "review",
        "skill",
        "sonarqube",
        "storage",
        "validation",
      ].sort(),
    );
  });

  it("keeps every entry translated in both locales with no raw placeholders left", () => {
    for (const [key, entry] of Object.entries(ERROR_CATALOG)) {
      expect(entry.en.trim().length, `en for ${key}`).toBeGreaterThan(0);
      expect(entry.pt.trim().length, `pt for ${key}`).toBeGreaterThan(0);
      expect(entry.pt, `pt for ${key} repeats the English text`).not.toBe(entry.en);
    }
  });
});

describe("resolveErrorDetail", () => {
  it("resolves a known key with locale-aware currency formatting", () => {
    const detail: ApiErrorDetail = {
      error_key: "budget.estimated_cost_exceeds_max",
      params: { estimated_cost_usd: 1.25, max_spend_usd: 0.5 },
    };

    expect(resolveErrorDetail(detail, "en-US")).toBe(
      "Estimated cost of $1.25 exceeds the maximum spend of $0.50.",
    );
    expect(resolveErrorDetail(detail, "pt-BR")).toContain("custo estimado");
    expect(resolveErrorDetail(detail, "pt-BR")).toContain("US$");
  });

  it("formats plain numbers in the locale convention", () => {
    const detail: ApiErrorDetail = {
      error_key: "budget.context_exceeds_max",
      params: { estimated_tokens: 123456, max_context_tokens: 60000 },
    };

    expect(resolveErrorDetail(detail, "en-US")).toContain("123,456");
    expect(resolveErrorDetail(detail, "pt-BR")).toContain("123.456");
  });

  it("falls back to a generic sentence carrying the raw key", () => {
    const detail: ApiErrorDetail = { error_key: "brand_new.not_catalogued", params: {} };

    expect(resolveErrorDetail(detail, "en-US")).toBe("Something went wrong. (brand_new.not_catalogued)".replace("_", "_"));
    expect(resolveErrorDetail(detail, "pt-BR")).toContain("Algo deu errado");
    expect(resolveErrorDetail(detail, "pt-BR")).toContain("brand_new.not_catalogued".replace("_", "_"));
  });

  it("drops unknown params instead of leaking raw placeholders", () => {
    const detail: ApiErrorDetail = {
      error_key: "project.not_found",
      params: { project_id: "abc", future_param: "ignored" },
    };

    const text = resolveErrorDetail(detail, "en-US");
    expect(text).toBe('Project "abc" does not exist.');
    expect(text).not.toContain("{future_param}");
  });

  it("joins an array of details with '; '", () => {
    const detail: ApiErrorDetail[] = [
      { error_key: "validation.invalid_field", params: { field: "budget.max_spend_usd" } },
      { error_key: "validation.invalid_field", params: { field: "budget.warn_above_usd" } },
    ];

    expect(resolveErrorDetails(detail, "en-US")).toBe(
      "The field budget.max_spend_usd is invalid.; The field budget.warn_above_usd is invalid.",
    );
  });
});

describe("resolveApiError", () => {
  it("resolves an ApiError-like value carrying the structured contract", () => {
    const error = {
      message: "provider.not_ready",
      errorKey: "provider.not_ready",
      params: { provider_id: "ollama" },
    };

    expect(resolveApiError(error, "pt-BR")).toContain("ollama");
  });

  it("keeps plain Error messages as-is (network failures are already human)", () => {
    expect(resolveApiError(new TypeError("Failed to fetch"), "pt-BR")).toBe("Failed to fetch");
  });

  it("falls back to a generic sentence for non-error values", () => {
    expect(resolveApiError(undefined, "en-US")).toBe("Something went wrong.");
    expect(resolveApiError("boom", "pt-BR")).toBe("Algo deu errado.");
  });
});
