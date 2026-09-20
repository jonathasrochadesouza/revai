import { describe, expect, it } from "vitest";

import { translate } from "@/lib/i18n";
import { enUS } from "@/lib/i18n/en-US";
import { ptBR } from "@/lib/i18n/pt-BR";

/**
 * Values that are proper nouns or technical terms and therefore legitimately
 * identical in both locales.
 */
const SAME_IN_BOTH = new Set([
  "common.engine",
  "common.skillsPrompts",
  "common.menu",
  "skills.tab.skills",
  "skills.tab.prompts",
  "skills.marketplace.title",
  "skills.installed.count",
  "projects.branch",
  "review.base",
  "review.head",
  "review.checkstyle",
  "review.build",
  "review.metric.tokens",
  "settings.appearance.theme.lightDetail",
  "settings.appearance.locale.enUS",
  "settings.appearance.locale.ptBR",
  "engine.unit.tokens",
  "engine.analyser.semgrep",
  "engine.analyser.ruff",
  "engine.analyser.ruffDetail",
  "engine.analyser.eslint",
  "engine.analyser.eslintDetail",
  "engine.analyser.gitleaks",
  "engine.analyser.treesitter",
  "engine.analyser.checkstyle",
  "engine.analyser.checkstyleDetail",
  "engine.sonar.title",
  "engine.sonar.docker",
  "engine.sonar.scanner",
  "engine.sonar.scanner.maven",
  "engine.sonar.scanner.gradle",
  "agent.engine",
  "insights.category.performance",
]);

describe("i18n catalogs", () => {
  it("keeps the pt-BR catalog in structural parity with en-US", () => {
    expect(Object.keys(ptBR).sort()).toEqual(Object.keys(enUS).sort());
  });

  it("has no empty entries", () => {
    for (const [key, value] of Object.entries(ptBR)) {
      expect(value.trim().length, `pt-BR entry "${key}" is empty`).toBeGreaterThan(0);
    }
  });

  it("translates every pt-BR entry outside the known proper nouns", () => {
    for (const [key, value] of Object.entries(ptBR)) {
      if (SAME_IN_BOTH.has(key)) continue;
      expect(value, `pt-BR entry "${key}" repeats the en-US text`).not.toBe(
        enUS[key as keyof typeof enUS],
      );
    }
  });

  it("interpolates parameters at render time", () => {
    const minutes = translate("pt-BR", "time.minutesAgo", { count: 5 });
    expect(minutes).toBe("5min atrás");
    expect(minutes.includes("{")).toBe(false);

    const tokens = translate("pt-BR", "review.status.completedTokens", { tokens: "1.2k" });
    expect(tokens).toBe("Concluída · 1.2k tokens");

    const english = translate("en-US", "insights.total", { count: 9 });
    expect(english).toBe("9 total");
  });
});
