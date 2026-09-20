/**
 * Settings › Skills — the marketplace gallery and the installed skills list.
 *
 * Two independent units:
 *
 * - **Marketplace** searches skills.sh on demand (never automatically), and
 *   installs go through a mandatory preview: the full SKILL.md body renders
 *   before the install button unlocks, with the focus selector (review / fix
 *   / both) alongside.
 * - **Installed** rows toggle, re-focus, update (manual only — the new body
 *   is fetched and pinned server-side), and uninstall. Update availability is
 *   only known after an explicit "check for updates".
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, TextInput } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import {
  api,
  type InstalledSkill,
  type MarketplaceSkill,
  type SkillFocus,
  type SkillPreview,
} from "@/lib/api";
import { useApiErrorText } from "@/lib/use-api-error-text";

const SEARCH_SUGGESTIONS = ["code review", "security", "testing", "performance"];

type BadgeInfo = { label: string; tone: BadgeTone };

function focusBadge(focus: SkillFocus, labels: Record<SkillFocus, string>): BadgeInfo {
  if (focus === "review") return { label: labels.review, tone: "info" };
  if (focus === "fix") return { label: labels.fix, tone: "medium" };
  return { label: labels.both, tone: "neutral" };
}

export function SkillsTab({ initial }: { initial: InstalledSkill[] }) {
  const [installed, setInstalled] = useState<InstalledSkill[]>(initial);

  const onInstalled = useCallback((skill: InstalledSkill) => {
    setInstalled((current) =>
      current.some((item) => item.id === skill.id)
        ? current.map((item) => (item.id === skill.id ? skill : item))
        : [...current, skill],
    );
  }, []);

  const onRemoved = useCallback((skillId: string) => {
    setInstalled((current) => current.filter((item) => item.id !== skillId));
  }, []);

  const onReplaced = useCallback((skill: InstalledSkill) => {
    setInstalled((current) => current.map((item) => (item.id === skill.id ? skill : item)));
  }, []);

  return (
    <>
      <MarketplaceCard installed={installed} onInstalled={onInstalled} />
      <InstalledCard
        installed={installed}
        onReplaced={onReplaced}
        onRemoved={onRemoved}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Marketplace
// ---------------------------------------------------------------------------

function MarketplaceCard({
  installed,
  onInstalled,
}: {
  installed: InstalledSkill[];
  onInstalled: (skill: InstalledSkill) => void;
}) {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MarketplaceSkill[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(term: string) {
    const trimmed = term.trim();
    if (trimmed.length < 2) return;
    setSearching(true);
    setError(null);
    try {
      const response = await api.searchMarketplace(trimmed);
      setResults(response.skills);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setSearching(false);
    }
  }

  const installedIds = new Set(installed.map((skill) => skill.id));

  return (
    <Card className="mb-3.5">
      <CardHeader title={t("skills.marketplace.title")} icon={MARKETPLACE_ICON} />
      <CardBody>
        <p className="mb-4 text-[12.5px] leading-relaxed text-ink-muted">
          {t("skills.marketplace.intro")}
        </p>

        <form
          className="mb-4 flex items-end gap-2.5 border-b border-line pb-4"
          onSubmit={(event) => {
            event.preventDefault();
            void search(query);
          }}
        >
          <div className="min-w-0 flex-1">
            <Field label={t("skills.marketplace.title")} htmlFor="marketplace-search">
              <TextInput
                id="marketplace-search"
                placeholder={t("skills.marketplace.searchPlaceholder")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </Field>
          </div>
          <Button variant="primary" type="submit" disabled={searching || query.trim().length < 2}>
            {searching ? t("skills.marketplace.searching") : t("skills.marketplace.search")}
          </Button>
        </form>

        {!results && !searching && (
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-muted">
            <span>{t("skills.marketplace.suggestions")}</span>
            {SEARCH_SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => {
                  setQuery(suggestion);
                  void search(suggestion);
                }}
                className="rounded-full border border-line bg-canvas px-2.5 py-1 transition-colors hover:border-ink"
              >
                “{suggestion}”
              </button>
            ))}
          </div>
        )}

        {error && (
          <p className="rounded-control border border-critical-line bg-critical-surface px-3 py-2 text-[12px] text-critical">
            {error}
          </p>
        )}

        {results && (
          <div className="flex flex-col gap-2.5">
            {results.length === 0 && (
              <p className="text-[12.5px] text-ink-muted">{t("skills.marketplace.empty")}</p>
            )}
            {results.map((skill) => (
              <MarketplaceRow
                key={`${skill.source}/${skill.id}`}
                skill={skill}
                alreadyInstalled={installedIds.has(skill.id)}
                onInstalled={onInstalled}
              />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function MarketplaceRow({
  skill,
  alreadyInstalled,
  onInstalled,
}: {
  skill: MarketplaceSkill;
  alreadyInstalled: boolean;
  onInstalled: (skill: InstalledSkill) => void;
}) {
  const { t } = useUiText();
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <div className="flex items-start gap-3 rounded-control border border-line bg-canvas px-3.5 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[13px] font-semibold">{skill.name}</span>
          <span className="shrink-0 truncate text-[11px] text-ink-subtle">{skill.source}</span>
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">
          {skill.description || t("skills.marketplace.noDescription")}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {skill.installs !== null && (
          <span className="text-[11px] text-ink-subtle">
            {t("skills.marketplace.installs", { count: skill.installs.toLocaleString() })}
          </span>
        )}
        {alreadyInstalled ? (
          <Badge tone="success">{t("skills.marketplace.installed")}</Badge>
        ) : (
          <Button
            variant="ghost"
            className="px-3 py-1.5 text-[12px]"
            onClick={() => setDialogOpen(true)}
          >
            {t("skills.marketplace.install")}
          </Button>
        )}
      </div>
      {dialogOpen && (
        <InstallDialog skill={skill} onClose={() => setDialogOpen(false)} onInstalled={onInstalled} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Install dialog (preview + focus)
// ---------------------------------------------------------------------------

function InstallDialog({
  skill,
  onClose,
  onInstalled,
}: {
  skill: MarketplaceSkill;
  onClose: () => void;
  onInstalled: (skill: InstalledSkill) => void;
}) {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const [focus, setFocus] = useState<SkillFocus>("both");
  const [preview, setPreview] = useState<SkillPreview | null>(null);
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .previewSkill(skill.source, skill.id)
      .then((loaded) => {
        if (!cancelled) setPreview(loaded);
      })
      .catch((cause) => {
        if (!cancelled) setError(errorText(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [skill.source, skill.id, errorText]);

  async function confirm() {
    if (!preview) return;
    setInstalling(true);
    setError(null);
    try {
      const installedSkill = await api.installSkill({
        source: skill.source,
        skill_id: skill.id,
        focus,
      });
      onInstalled(installedSkill);
      onClose();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setInstalling(false);
    }
  }

  return (
    <div role="presentation" className="fixed inset-0 z-50 grid place-items-center bg-black/25 p-4">
      <section
        role="dialog"
        aria-modal="true"
        aria-label={t("skills.preview.title", { name: skill.name })}
        className="flex max-h-[85vh] w-full max-w-[640px] flex-col border border-line bg-paper shadow-2xl"
      >
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-[15px] font-semibold">
            {t("skills.preview.title", { name: skill.name })}
          </h2>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">
            {t("skills.preview.body")}
          </p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {!preview ? (
            <p className="text-[12.5px] text-ink-muted">{t("skills.preview.loading")}</p>
          ) : (
            <>
              <p className="mb-3 text-[12px] text-ink-muted">
                <span className="font-semibold">{t("skills.preview.instructions")}</span>
                {" · "}
                <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[11px] text-low">
                  {preview.source}
                </code>
                {preview.license && (
                  <>
                    {" · "}
                    <span className="text-ink-subtle">{preview.license}</span>
                  </>
                )}
              </p>
              <pre className="whitespace-pre-wrap rounded-control border border-line bg-canvas px-3.5 py-3 font-mono text-[11.5px] leading-relaxed text-ink">
                {preview.body}
              </pre>
            </>
          )}
          {error && (
            <p className="mt-3 rounded-control border border-critical-line bg-critical-surface px-3 py-2 text-[12px] text-critical">
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2.5 border-t border-line px-5 py-4">
          <label htmlFor="install-focus" className="text-[12.5px] font-medium text-ink-muted">
            {t("skills.focus.label")}
          </label>
          <select
            id="install-focus"
            value={focus}
            onChange={(event) => setFocus(event.target.value as SkillFocus)}
            className="rounded-control border border-line-strong bg-paper px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-ink"
          >
            <option value="review">{t("skills.focus.review")}</option>
            <option value="fix">{t("skills.focus.fix")}</option>
            <option value="both">{t("skills.focus.both")}</option>
          </select>
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="primary"
              disabled={!preview || installing}
              onClick={() => void confirm()}
            >
              {installing ? t("skills.preview.installing") : t("skills.preview.confirm")}
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Installed skills
// ---------------------------------------------------------------------------

function InstalledCard({
  installed,
  onReplaced,
  onRemoved,
}: {
  installed: InstalledSkill[];
  onReplaced: (skill: InstalledSkill) => void;
  onRemoved: (skillId: string) => void;
}) {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const [checking, setChecking] = useState(false);
  const [updates, setUpdates] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function checkUpdates() {
    setChecking(true);
    setError(null);
    setNotice(null);
    try {
      const response = await api.checkSkillUpdates();
      setUpdates(
        Object.fromEntries(response.updates.map((entry) => [entry.skill_id, entry.update_available])),
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setChecking(false);
    }
  }

  return (
    <Card className="mb-3.5">
      <CardHeader
        title={t("skills.installed.title")}
        icon={INSTALLED_ICON}
        aside={t("skills.installed.count", { count: installed.length })}
      />
      <CardBody>
        <p className="mb-4 text-[12.5px] leading-relaxed text-ink-muted">
          {t("skills.installed.intro")}
        </p>

        {installed.length === 0 ? (
          <div className="rounded-control border border-dashed border-line px-4 py-6 text-center">
            <p className="text-[13px] font-semibold">{t("skills.installed.empty.title")}</p>
            <p className="mt-1 text-[12px] text-ink-muted">{t("skills.installed.empty.body")}</p>
          </div>
        ) : (
          <>
            <div className="mb-3.5 flex justify-end gap-2.5">
              {notice && (
                <span className="self-center text-[12px] text-success">{notice}</span>
              )}
              <Button
                variant="ghost"
                onClick={() => void checkUpdates()}
                disabled={checking}
              >
                {checking ? t("skills.installed.checking") : t("skills.installed.checkUpdates")}
              </Button>
            </div>

            <div className="flex flex-col gap-2.5">
              {installed.map((skill) => (
                <InstalledRow
                  key={skill.id}
                  skill={skill}
                  updateAvailable={updates[skill.id] ?? false}
                  onReplaced={onReplaced}
                  onRemoved={onRemoved}
                  onNotice={setNotice}
                />
              ))}
            </div>
          </>
        )}

        {error && (
          <p className="mt-3 rounded-control border border-critical-line bg-critical-surface px-3 py-2 text-[12px] text-critical">
            {error}
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function InstalledRow({
  skill,
  updateAvailable,
  onReplaced,
  onRemoved,
  onNotice,
}: {
  skill: InstalledSkill;
  updateAvailable: boolean;
  onReplaced: (skill: InstalledSkill) => void;
  onRemoved: (skillId: string) => void;
  onNotice: (message: string | null) => void;
}) {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const [busy, setBusy] = useState<null | "toggle" | "focus" | "update">(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);

  async function patch(input: { enabled?: boolean; focus?: SkillFocus }, kind: typeof busy) {
    setBusy(kind);
    setRowError(null);
    try {
      onReplaced(await api.updateSkill(skill.id, input));
    } catch (cause) {
      setRowError(errorText(cause));
    } finally {
      setBusy(null);
    }
  }

  async function update() {
    setBusy("update");
    setRowError(null);
    onNotice(null);
    try {
      const response = await api.refreshSkill(skill.id);
      onReplaced(response.skill);
      onNotice(t("skills.installed.updated"));
    } catch (cause) {
      setRowError(errorText(cause));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy(null);
    setRowError(null);
    try {
      await api.uninstallSkill(skill.id);
      onRemoved(skill.id);
    } catch (cause) {
      setRowError(errorText(cause));
    }
  }

  const badge = focusBadge(skill.focus, {
    review: t("skills.focus.review"),
    fix: t("skills.focus.fix"),
    both: t("skills.focus.both"),
  });

  return (
    <div className="rounded-control border border-line bg-canvas px-3.5 py-3">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-[13px] font-semibold">{skill.name}</span>
            <Badge tone={badge.tone}>{badge.label}</Badge>
            {updateAvailable && (
              <Badge tone="medium">{t("skills.installed.updateAvailable")}</Badge>
            )}
          </div>
          <p className="mt-1 truncate text-[11px] text-ink-subtle">
            {skill.source} · {skill.id}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <label className="flex items-center gap-2 text-[12px] text-ink-muted">
            <span className="sr-only">{t("skills.installed.enabled")}</span>
            {t("skills.installed.enabled")}
          </label>
          <Switch
            checked={skill.enabled}
            disabled={busy !== null}
            label={t("skills.installed.enabled")}
            onChange={(enabled) => void patch({ enabled }, "toggle")}
          />
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2 border-t border-line pt-2.5">
        <label htmlFor={`${skill.id}-focus`} className="text-[12px] font-medium text-ink-muted">
          {t("skills.focus.label")}
        </label>
        <select
          id={`${skill.id}-focus`}
          value={skill.focus}
          disabled={busy !== null}
          onChange={(event) =>
            void patch({ focus: event.target.value as SkillFocus }, "focus")
          }
          className="rounded-control border border-line-strong bg-paper px-2.5 py-1.5 text-[12px] text-ink outline-none focus:border-ink"
        >
          <option value="review">{t("skills.focus.review")}</option>
          <option value="fix">{t("skills.focus.fix")}</option>
          <option value="both">{t("skills.focus.both")}</option>
        </select>

        <div className="ml-auto flex items-center gap-2">
          {rowError && (
            <span className="max-w-[260px] truncate text-[11.5px] text-critical" title={rowError}>
              {rowError}
            </span>
          )}
          <Button
            variant="ghost"
            className="px-3 py-1.5 text-[12px]"
            disabled={busy !== null}
            onClick={() => void update()}
          >
            {busy === "update"
              ? t("skills.installed.updating")
              : t("skills.installed.update")}
          </Button>
          <Button
            variant="danger"
            className="px-3 py-1.5 text-[12px]"
            onClick={() => setConfirmDelete(true)}
            disabled={busy !== null}
          >
            {t("skills.installed.uninstall")}
          </Button>
        </div>
      </div>

      {confirmDelete && (
        <ConfirmDialog
          name={skill.name}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={async () => {
            setConfirmDelete(false);
            await remove();
          }}
        />
      )}
    </div>
  );
}

function ConfirmDialog({
  name,
  onCancel,
  onConfirm,
}: {
  name: string;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  const { t } = useUiText();
  return (
    <div role="presentation" className="fixed inset-0 z-50 grid place-items-center bg-black/25 p-4">
      <section
        role="dialog"
        aria-modal="true"
        aria-label={t("skills.deleteDialog.title", { name })}
        className="w-full max-w-[420px] border border-line bg-paper shadow-2xl"
      >
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-[15px] font-semibold">
            {t("skills.deleteDialog.title", { name })}
          </h2>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">
            {t("skills.deleteDialog.body")}
          </p>
        </div>
        <div className="flex justify-end gap-2 border-t border-line px-5 py-4">
          <Button variant="ghost" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" onClick={() => void onConfirm()}>
            {t("skills.installed.uninstall")}
          </Button>
        </div>
      </section>
    </div>
  );
}

// --- icons -------------------------------------------------------------------

const MARKETPLACE_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

const INSTALLED_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
    <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
  </svg>
);
