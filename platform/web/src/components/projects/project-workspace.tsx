"use client";

import {
  Activity,
  ArrowRight,
  Boxes,
  Check,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  CircleDollarSign,
  CircleX,
  ClipboardCheck,
  Code2,
  Copy,
  FolderOpen,
  FolderGit2,
  GitBranch,
  GitCompareArrows,
  HardDrive,
  LoaderCircle,
  ScanSearch,
  Search,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import Link from "next/link";
import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactElement,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useToast } from "@/components/toast-provider";
import { useUiText } from "@/components/ui-preference-bootstrap";
import {
  type FileLayout,
  type FileUniverse,
  ReviewFileBrowser,
} from "@/components/projects/review-file-browser";
import { BranchSelect } from "@/components/ui/branch-select";
import { DiffViewer } from "@/components/diff/diff-viewer";
import { FindingCard } from "@/components/findings/finding-card";
import { useApiErrorText } from "@/lib/use-api-error-text";
import { InfoTooltip } from "@/components/ui/info-tooltip";

import {
  api,
  type AnalyzerRun,
  type DeterministicReview,
  type DiffPreview,
  type Finding,
  type Project,
  type ProjectTree,
  type PromptScenario,
  type ProviderHealth,
  type Review,
  type ReviewMode,
  type ReviewScope,
  type ReviewStreamEvent,
  type RevaiConfig,
  isUsable,
} from "@/lib/api";

type ProjectFilter = "all" | "active" | "archived";
type DialogMode = "open" | "clone" | null;

const AVATAR_TONES = [
  "bg-low-surface text-low border-low-line",
  "bg-success-surface text-success border-success-line",
  "bg-medium-surface text-medium border-medium-line",
  "bg-critical-surface text-critical border-critical-line",
] as const;

function initials(name: string): string {
  return name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function relativeDate(value: string, renderedAt: string, t: (key: string, params?: Record<string, string | number>) => string): string {
  const elapsed = new Date(renderedAt).getTime() - new Date(value).getTime();
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 1) return t("time.justNow");
  if (minutes < 60) return t("time.minutesAgo", { count: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("time.hoursAgo", { count: hours });
  const days = Math.floor(hours / 24);
  return t("time.daysAgo", { count: days });
}

function formatTokens(tokens: number): string {
  if (tokens < 1_000) return String(tokens);
  return `${(tokens / 1_000).toFixed(tokens < 10_000 ? 1 : 0)}k`;
}

export function ProjectWorkspace({
  initialProjects,
  initialError,
  renderedAt,
}: {
  initialProjects: Project[];
  initialError?: string;
  renderedAt: string;
}) {
  const { t } = useUiText();
  const toast = useToast();
  const errorText = useApiErrorText();
  const [projects, setProjects] = useState(initialProjects);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ProjectFilter>("all");
  const [dialog, setDialog] = useState<DialogMode>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // A failure the projects page itself fetched with (server component) is
  // replayed once as a toast, instead of a permanently resident banner.
  useEffect(() => {
    if (initialError) toast.push(initialError);
  }, [initialError, toast]);

  const visibleProjects = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return projects.filter((project) => {
      if (filter === "active" && project.archived) return false;
      if (filter === "archived" && !project.archived) return false;
      return (
        !normalized ||
        project.name.toLowerCase().includes(normalized) ||
        project.path.toLowerCase().includes(normalized) ||
        project.current_branch?.toLowerCase().includes(normalized)
      );
    });
  }, [filter, projects, query]);

  useEffect(() => {
    const focusSearch = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const refresh = useCallback(async () => {
    const response = await api.getProjects();
    setProjects(response.projects);
  }, []);

  return (
    <main className="mx-auto w-full max-w-[1280px] px-5 pb-20 pt-9 sm:px-7">
      <section className="mb-8 flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
        <div>
          <h1 className="mb-1.5 text-[29px] font-bold leading-tight">
            {t("projects.title")}
          </h1>
          <p className="max-w-[64ch] text-[14px] leading-relaxed text-ink-muted">
            {t("projects.subtitle")}
          </p>
        </div>
        <label className="flex h-10 w-full items-center gap-2.5 rounded-control border border-line-strong bg-paper px-3 text-ink-subtle lg:w-[310px]">
          <Search aria-hidden className="size-4 shrink-0" strokeWidth={1.8} />
          <span className="sr-only">{t("projects.searchProjects")}</span>
          <input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("projects.searchProjects")}
            className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-subtle"
          />
          <kbd className="rounded-chip border border-line px-1.5 py-0.5 text-[10px]">
            Ctrl K
          </kbd>
        </label>
      </section>

      <OnboardingChecklist hasProjects={projects.length > 0} />

      <section aria-label={t("projects.addRepository")} className="mb-8 grid gap-3 md:grid-cols-2">
        <EntryAction
          icon={<HardDrive className="size-5" strokeWidth={1.8} />}
          title={t("projects.openLocalFolder")}
          description={t("projects.openLocalFolderDescription")}
          action={t("projects.openLocalFolderAction")}
          onClick={() => setDialog("open")}
        />
        <EntryAction
          icon={<Copy className="size-5" strokeWidth={1.8} />}
          title={t("projects.cloneFromRemote")}
          description={t("projects.cloneFromRemoteDescription")}
          action={t("projects.cloneFromRemoteAction")}
          onClick={() => setDialog("clone")}
        />
      </section>

      <section className="surface overflow-hidden">
        <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h2 className="flex items-center gap-2 text-[14px] font-semibold">
            {t("projects.yourProjects")}
            <span className="numeric rounded-chip bg-canvas px-2 py-0.5 text-[10.5px] font-medium text-ink-muted">
              {projects.length}
            </span>
          </h2>
          <div className="flex rounded-control bg-canvas p-0.5">
            {(["all", "active", "archived"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                aria-pressed={filter === value}
                className={`rounded-chip px-3 py-1.5 text-[11.5px] font-medium transition-colors ${
                  filter === value
                    ? "border border-line bg-paper text-ink"
                    : "border border-transparent text-ink-subtle hover:text-ink"
                }`}
              >
                {t(value === "all" ? "projects.filterAll" : value === "active" ? "projects.filterActive" : "projects.filterArchived")}
              </button>
            ))}
          </div>
        </div>

        <div className="hidden grid-cols-[minmax(260px,1fr)_180px_170px_90px] gap-4 border-b border-line bg-sunken px-5 py-2.5 text-[10px] font-semibold uppercase text-ink-subtle md:grid">
          <span>{t("projects.repository")}</span>
          <span>{t("projects.branch")}</span>
          <span>{t("projects.languages")}</span>
          <span className="text-right">{t("projects.added")}</span>
        </div>

        {visibleProjects.length ? (
          visibleProjects.map((project, index) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}/review`}
              className="grid w-full gap-3 border-b border-line bg-paper px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-canvas md:grid-cols-[minmax(260px,1fr)_180px_170px_90px] md:items-center md:gap-4"
            >
              <span className="flex min-w-0 items-center gap-3">
                <span
                  className={`grid size-9 shrink-0 place-items-center rounded-control border text-[11px] font-bold ${AVATAR_TONES[index % AVATAR_TONES.length]}`}
                >
                  {initials(project.name)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-[13.5px] font-semibold">
                    {project.name}
                  </span>
                  <span className="numeric block truncate text-[10.5px] text-ink-subtle">
                    {project.path}
                  </span>
                </span>
              </span>
              <span className="flex min-w-0 items-center gap-1.5 font-mono text-[11.5px] text-ink-muted">
                <GitBranch className="size-3.5 shrink-0 text-low" />
                <span className="truncate">
                  {project.current_branch ?? "detached HEAD"}
                </span>
              </span>
              <span className="truncate text-[11.5px] text-ink-muted">
                {project.languages.join(", ") || t("projects.notDetected")}
              </span>
              <span className="numeric text-[11px] text-ink-subtle md:text-right">
                {relativeDate(project.created_at, renderedAt, t)}
              </span>
            </Link>
          ))
        ) : (
          <EmptyProjects
            hasProjects={projects.length > 0}
            onOpen={() => setDialog("open")}
          />
        )}
      </section>

      {dialog && (
        <RepositoryDialog
          mode={dialog}
          onClose={() => setDialog(null)}
          onCreated={async () => {
            setDialog(null);
            try {
              await refresh();
            } catch (error) {
              toast.push(errorText(error));
            }
          }}
        />
      )}
    </main>
  );
}

function EntryAction({
  icon,
  title,
  description,
  action,
  onClick,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group surface flex min-h-[126px] items-start gap-4 p-5 text-left transition-[border-color,background-color] hover:border-line-strong hover:bg-sunken"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-control border border-line bg-canvas text-ink-muted">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="mb-1 block text-[14px] font-semibold">{title}</span>
        <span className="mb-3 block text-[12.5px] leading-relaxed text-ink-muted">
          {description}
        </span>
        <span className="flex items-center gap-1.5 text-[11.5px] font-semibold text-low">
          {action}
          <ArrowRight
            className="size-3.5 transition-transform group-hover:translate-x-0.5"
            strokeWidth={2}
          />
        </span>
      </span>
    </button>
  );
}

function EmptyProjects({
  hasProjects,
  onOpen,
}: {
  hasProjects: boolean;
  onOpen: () => void;
}) {
  const { t } = useUiText();
  return (
    <div className="grid min-h-48 place-items-center px-5 py-10 text-center">
      <div>
        <FolderGit2 className="mx-auto mb-3 size-7 text-ink-subtle" strokeWidth={1.5} />
        <p className="mb-1 text-[13px] font-semibold">
          {hasProjects ? t("projects.noMatchView") : t("projects.noRepositories")}
        </p>
        <p className="mb-4 text-[12px] text-ink-muted">
          {hasProjects
            ? t("projects.tryDifferentSearch")
            : t("projects.openLocalGitFolder")}
        </p>
        {!hasProjects && (
          <button
            type="button"
            onClick={onOpen}
            className="rounded-control bg-ink px-3.5 py-2 text-[11.5px] font-semibold text-paper hover:bg-ink-hover"
          >
            {t("projects.openRepository")}
          </button>
        )}
      </div>
    </div>
  );
}

function OnboardingChecklist({ hasProjects }: { hasProjects: boolean }) {
  const { t } = useUiText();
  const [config, setConfig] = useState<RevaiConfig | null>(null);
  const [providerReady, setProviderReady] = useState<boolean | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [collapsed, setCollapsed] = useState(true);
  const collapseInitialized = useRef(false);

  useEffect(() => {
    let active = true;
    api.getConfig()
      .then(async (saved) => {
        if (!active) return null;
        setConfig(saved.config);
        return api.verifyProvider(saved.config.engine.provider_id);
      })
      .then((health) => {
        if (active) setProviderReady(health ? isUsable(health) : false);
      })
      .catch(() => {
        if (active) setProviderReady(false);
      })
      .finally(() => {
        if (active) setLoaded(true);
      });
    return () => { active = false; };
  }, []);

  const steps = [
    { label: t("projects.stepConfigureEngine"), done: Boolean(config?.engine.model), href: "/settings/engine" },
    { label: t("projects.stepVerifyProvider"), done: providerReady === true, href: "/settings/engine" },
    { label: t("projects.stepAddRepository"), done: hasProjects, href: "#repositories" },
  ];
  const allDone = steps.every((step) => step.done);

  useEffect(() => {
    if (loaded && !collapseInitialized.current) {
      collapseInitialized.current = true;
      setCollapsed(allDone);
    }
  }, [loaded, allDone]);

  if (!loaded) return null;

  return (
    <section className="mb-6 border border-line bg-paper px-5 py-4" aria-label={t("projects.gettingStarted")}>
      <button
        type="button"
        onClick={() => setCollapsed((current) => !current)}
        aria-expanded={!collapsed}
        className={`flex w-full items-center gap-2 text-left ${collapsed ? "" : "mb-3"}`}
      >
        <ClipboardCheck className="size-4 text-low" />
        <h2 className="flex-1 text-[13px] font-semibold">{t("projects.gettingStartedTitle")}</h2>
        {allDone && (
          <span className="rounded-chip bg-success-surface px-2 py-0.5 text-[10px] font-medium text-success">
            {t("projects.complete")}
          </span>
        )}
        {collapsed ? (
          <ChevronDown className="size-4 text-ink-subtle" />
        ) : (
          <ChevronUp className="size-4 text-ink-subtle" />
        )}
      </button>
      {!collapsed && (
        <div className="grid gap-2 sm:grid-cols-3">
          {steps.map((step) => (
            <a key={step.label} href={step.href} className="flex items-center gap-2 border border-line px-3 py-2 text-[11.5px] hover:bg-canvas">
              <span className={`grid size-5 place-items-center rounded-full ${step.done ? "bg-success-surface text-success" : "bg-canvas text-ink-subtle"}`}>
                {step.done ? <Check className="size-3" /> : ""}
              </span>
              <span>{step.label}</span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function RepositoryDialog({
  mode,
  onClose,
  onCreated,
}: {
  mode: Exclude<DialogMode, null>;
  onClose: () => void;
  onCreated: (project: Project) => void;
}) {
  const { t } = useUiText();
  const toast = useToast();
  const errorText = useApiErrorText();
  const [value, setValue] = useState("");
  const [destination, setDestination] = useState("");
  const [pending, setPending] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!value.trim() || (mode === "clone" && !destination.trim())) return;
    setPending(true);
    try {
      const project =
        mode === "open"
          ? await api.openProject(value.trim())
          : await api.cloneProject(value.trim(), destination.trim());
      onCreated(project);
    } catch (cause) {
      toast.push(errorText(cause));
      setPending(false);
    }
  };

  const closeOnEscape = (event: ReactKeyboardEvent) => {
    if (event.key === "Escape" && !pending && !browsing) onClose();
  };

  const isOpen = mode === "open";
  const busy = pending || browsing;
  const canSubmit = Boolean(
    value.trim() && (isOpen || destination.trim()),
  );

  const browse = async () => {
    setBrowsing(true);
    try {
      const result = await api.pickProjectFolder();
      if (result.path) {
        if (isOpen) setValue(result.path);
        else setDestination(result.path);
      }
    } catch (cause) {
      toast.push(errorText(cause));
    } finally {
      setBrowsing(false);
    }
  };

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 grid place-items-center bg-black/25 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
      onKeyDown={closeOnEscape}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="repository-dialog-title"
        className="w-full max-w-[500px] rounded-panel border border-line bg-paper shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 id="repository-dialog-title" className="text-[15px] font-semibold">
              {isOpen ? t("projects.dialog.openTitle") : t("projects.dialog.cloneTitle")}
            </h2>
            <p className="mt-1 text-[12px] text-ink-muted">
              {isOpen
                ? t("projects.dialog.openDescription")
                : t("projects.dialog.cloneDescription")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label={t("common.closeDialog")}
            className="rounded-control p-1.5 text-ink-subtle hover:bg-canvas hover:text-ink disabled:opacity-40"
          >
            <X className="size-4" />
          </button>
        </div>
        <form onSubmit={submit} className="p-5">
          <label className="mb-1.5 block text-[11.5px] font-semibold" htmlFor="repository-source">
            {isOpen ? t("projects.dialog.folderPath") : t("projects.dialog.repositoryUrl")}
          </label>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              id="repository-source"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder={
                isOpen
                  ? "C:\\Dev\\Repositories\\my-project"
                  : "https://github.com/company/repository.git"
              }
              disabled={busy}
              required
              className="h-10 min-w-0 flex-1 rounded-control border border-line-strong bg-paper px-3 font-mono text-[12px] outline-none placeholder:text-ink-subtle focus:border-ink disabled:bg-canvas"
            />
            {isOpen && (
              <button
                type="button"
                onClick={() => void browse()}
                disabled={busy}
                className="flex h-10 shrink-0 items-center gap-2 rounded-control border border-line-strong px-3 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink disabled:opacity-40"
              >
                {browsing ? (
                  <LoaderCircle className="size-3.5 animate-spin" />
                ) : (
                  <FolderOpen className="size-3.5" />
                )}
                {browsing ? t("projects.dialog.selecting") : t("projects.dialog.browse")}
              </button>
            )}
          </div>
          {!isOpen && (
            <>
              <label
                className="mb-1.5 mt-4 block text-[11.5px] font-semibold"
                htmlFor="repository-destination"
              >
                {t("projects.dialog.saveIn")}
              </label>
              <div className="flex gap-2">
                <input
                  id="repository-destination"
                  value={destination}
                  onChange={(event) => setDestination(event.target.value)}
                  placeholder={"C:\\Dev\\Repositories"}
                  disabled={busy}
                  required
                  className="h-10 min-w-0 flex-1 rounded-control border border-line-strong bg-paper px-3 font-mono text-[12px] outline-none placeholder:text-ink-subtle focus:border-ink disabled:bg-canvas"
                />
                <button
                  type="button"
                  onClick={() => void browse()}
                  disabled={busy}
                  className="flex h-10 shrink-0 items-center gap-2 rounded-control border border-line-strong px-3 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink disabled:opacity-40"
                >
                  {browsing ? (
                    <LoaderCircle className="size-3.5 animate-spin" />
                  ) : (
                    <FolderOpen className="size-3.5" />
                  )}
                  {browsing ? t("projects.dialog.selecting") : t("projects.dialog.browse")}
                </button>
              </div>
            </>
          )}
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded-control border border-line-strong px-3.5 py-2 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas disabled:opacity-40"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={busy || !canSubmit}
              className="flex min-w-[88px] items-center justify-center gap-2 rounded-control bg-ink px-3.5 py-2 text-[11.5px] font-semibold text-paper hover:bg-ink-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending && <LoaderCircle className="size-3.5 animate-spin" />}
              {pending ? (isOpen ? t("projects.dialog.opening") : t("projects.dialog.cloning")) : isOpen ? t("projects.dialog.open") : t("projects.dialog.clone")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function RepositoryInspector({
  project,
  onError,
}: {
  project: Project;
  onError: (message: string) => void;
}) {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const defaultHead = project.current_branch ?? project.base_branch;
  const [base, setBase] = useState(project.base_branch);
  const [head, setHead] = useState(defaultHead);
  const [tree, setTree] = useState<ProjectTree | null>(null);
  const [branchPreview, setBranchPreview] = useState<DiffPreview | null>(null);
  const [scopedPreview, setScopedPreview] = useState<DiffPreview | null>(null);
  const [treeLoading, setTreeLoading] = useState(true);
  const [branchLoading, setBranchLoading] = useState(true);
  const [scopedLoading, setScopedLoading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [result, setResult] = useState<DeterministicReview | null>(null);
  const [cancelled, setCancelled] = useState(false);
  const [events, setEvents] = useState<ReviewStreamEvent[]>([]);
  const [config, setConfig] = useState<RevaiConfig | null>(null);
  const [providerHealth, setProviderHealth] = useState<ProviderHealth | null>(null);
  const [providerChecking, setProviderChecking] = useState(true);
  const [analyzerPreflight, setAnalyzerPreflight] = useState<Awaited<ReturnType<typeof api.getAnalyzerPreflight>> | null>(null);
  const [history, setHistory] = useState<Review[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [reviewMode, setReviewMode] = useState<ReviewMode>("both");
  const [reviewScope, setReviewScope] = useState<ReviewScope>("branch_diff");
  const [scenarios, setScenarios] = useState<PromptScenario[]>([]);
  const [scenarioId, setScenarioId] = useState<string>("");
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [fileUniverse, setFileUniverse] = useState<FileUniverse>("changed");
  const [fileLayout, setFileLayout] = useState<FileLayout>("flat");
  const [fileQuery, setFileQuery] = useState("");
  const reviewAbort = useRef<AbortController | null>(null);
  const activeReviewId = useRef<string | null>(null);
  const treeRequestId = useRef(0);
  const branchRequestId = useRef(0);
  const scopedRequestId = useRef(0);

  const preview = reviewScope === "branch_diff" ? branchPreview : scopedPreview;
  const loading = reviewScope === "branch_diff" ? branchLoading : scopedLoading;
  const changedFiles = useMemo(
    () => branchPreview?.files.map((file) => file.path) ?? [],
    [branchPreview],
  );

  useEffect(() => {
    return () => reviewAbort.current?.abort();
  }, []);

  // Prompt scenarios are global, so one cheap fetch per mount is enough. A
  // failure is silent by design: reviewing with the default prompts still works.
  useEffect(() => {
    let active = true;
    api
      .getPrompts()
      .then((response) => {
        if (active) setScenarios(response.scenarios);
      })
      .catch(() => {
        // Scenario picking is optional; never block the review panel on it.
      });
    return () => {
      active = false;
    };
  }, []);

  const fetchTree = useCallback(
    () => api.getProjectTree(project.id, head),
    [head, project.id],
  );
  const fetchBranchPreview = useCallback(
    () => api.getProjectDiff(project.id, base, head, "branch_diff"),
    [base, head, project.id],
  );
  const fetchScopedPreview = useCallback(
    () => api.getProjectDiff(project.id, base, head, reviewScope, selectedFiles),
    [base, head, project.id, reviewScope, selectedFiles],
  );

  const loadTree = useCallback(async () => {
    const requestId = ++treeRequestId.current;
    try {
      const nextTree = await fetchTree();
      if (requestId === treeRequestId.current) setTree(nextTree);
    } catch (error) {
      if (requestId === treeRequestId.current) onError(errorText(error));
    } finally {
      if (requestId === treeRequestId.current) setTreeLoading(false);
    }
  }, [errorText, fetchTree, onError]);

  const loadBranchPreview = useCallback(async () => {
    const requestId = ++branchRequestId.current;
    try {
      const nextPreview = await fetchBranchPreview();
      if (requestId === branchRequestId.current) setBranchPreview(nextPreview);
    } catch (error) {
      if (requestId === branchRequestId.current) onError(errorText(error));
    } finally {
      if (requestId === branchRequestId.current) setBranchLoading(false);
    }
  }, [errorText, fetchBranchPreview, onError]);

  const loadScopedPreview = useCallback(async () => {
    if (reviewScope === "branch_diff") return;
    const requestId = ++scopedRequestId.current;
    if (reviewScope === "selected_files" && selectedFiles.length === 0) return;
    try {
      const nextPreview = await fetchScopedPreview();
      if (requestId === scopedRequestId.current) setScopedPreview(nextPreview);
    } catch (error) {
      if (requestId === scopedRequestId.current) onError(errorText(error));
    } finally {
      if (requestId === scopedRequestId.current) setScopedLoading(false);
    }
  }, [errorText, fetchScopedPreview, onError, reviewScope, selectedFiles.length]);

  const load = useCallback(async () => {
    setTreeLoading(true);
    setBranchLoading(true);
    const shouldLoadScoped =
      reviewScope !== "branch_diff" &&
      (reviewScope !== "selected_files" || selectedFiles.length > 0);
    setScopedLoading(shouldLoadScoped);
    if (!shouldLoadScoped && reviewScope === "selected_files") setScopedPreview(null);
    const requests = [loadTree(), loadBranchPreview()];
    if (shouldLoadScoped) requests.push(loadScopedPreview());
    await Promise.all(requests);
  }, [loadBranchPreview, loadScopedPreview, loadTree, reviewScope, selectedFiles.length]);

  const loadHistory = useCallback(async () => {
    try {
      const response = await api.getProjectReviews(project.id);
      setHistory(response.reviews);
    } catch (error) {
      onError(errorText(error));
    }
  }, [errorText, onError, project.id]);

  useEffect(() => {
    let active = true;
    void api
      .getProjectReviews(project.id)
      .then((response) => {
        if (active) setHistory(response.reviews);
      })
      .catch((error: unknown) => {
        if (active) onError(errorText(error));
      });
    void api
      .getConfig()
      .then(async (response) => {
        if (!active) return null;
        setConfig(response.config);
        return api.verifyProvider(response.config.engine.provider_id);
      })
      .then((health) => {
        if (active && health) setProviderHealth(health);
      })
      .catch(() => {
        if (active) setProviderHealth(null);
      })
      .finally(() => {
        if (active) setProviderChecking(false);
      });
    void api.getAnalyzerPreflight(project.id).then((preflight) => {
      if (active) setAnalyzerPreflight(preflight);
    }).catch(() => {
      if (active) setAnalyzerPreflight(null);
    });

    return () => {
      active = false;
    };
  }, [errorText, onError, project.id]);

  useEffect(() => {
    const requestId = ++treeRequestId.current;
    void fetchTree()
      .then((nextTree) => {
        if (requestId === treeRequestId.current) setTree(nextTree);
      })
      .catch((error: unknown) => {
        if (requestId === treeRequestId.current) onError(errorText(error));
      })
      .finally(() => {
        if (requestId === treeRequestId.current) setTreeLoading(false);
      });
    return () => {
      treeRequestId.current += 1;
    };
  }, [errorText, fetchTree, onError]);

  useEffect(() => {
    const requestId = ++branchRequestId.current;
    void fetchBranchPreview()
      .then((nextPreview) => {
        if (requestId === branchRequestId.current) setBranchPreview(nextPreview);
      })
      .catch((error: unknown) => {
        if (requestId === branchRequestId.current) onError(errorText(error));
      })
      .finally(() => {
        if (requestId === branchRequestId.current) setBranchLoading(false);
      });
    return () => {
      branchRequestId.current += 1;
    };
  }, [errorText, fetchBranchPreview, onError]);

  useEffect(() => {
    if (
      reviewScope !== "branch_diff" &&
      (reviewScope !== "selected_files" || selectedFiles.length > 0)
    ) {
      const requestId = ++scopedRequestId.current;
      void fetchScopedPreview()
        .then((nextPreview) => {
          if (requestId === scopedRequestId.current) setScopedPreview(nextPreview);
        })
        .catch((error: unknown) => {
          if (requestId === scopedRequestId.current) onError(errorText(error));
        })
        .finally(() => {
          if (requestId === scopedRequestId.current) setScopedLoading(false);
        });
    }
    return () => {
      scopedRequestId.current += 1;
    };
  }, [errorText, fetchScopedPreview, onError, reviewScope, selectedFiles.length]);

  const runReview = async () => {
    if (reviewMode !== "static" && (!providerHealth || !isUsable(providerHealth))) {
      onError(
        providerHealth?.detail ??
          t("review.providerUnavailable"),
      );
      return;
    }
    const controller = new AbortController();
    reviewAbort.current?.abort();
    setCancelled(false);
    reviewAbort.current = controller;
    setReviewing(true);
    setResult(null);
    setEvents([]);
    try {
      if (reviewMode === "static") {
        const nextResult = await api.runDeterministicReview(
          project.id,
          base,
          head,
          reviewScope,
          selectedFiles,
        );
        setResult(nextResult);
        return;
      }
      const nextResult = await api.streamReview(
        project.id,
        base,
        head,
        reviewMode,
        reviewScope,
        selectedFiles,
        {
        scenarioId: scenarioId || undefined,
        signal: controller.signal,
        onEvent: (event) => {
          if (event.type === "review_queued") activeReviewId.current = event.review_id;
          setEvents((current) => {
            const last = current.at(-1);
            if (event.type === "delta" && last?.type === "delta") {
              return [...current.slice(0, -1), event];
            }
            return [...current, event].slice(-80);
          });
        },
        },
      );
      setResult(nextResult);
      activeReviewId.current = null;
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        onError(errorText(error));
      }
    } finally {
      void loadHistory();
      if (reviewAbort.current === controller) {
        reviewAbort.current = null;
        setReviewing(false);
      }
    }
  };

  const cancelReview = () => {
    const reviewId = activeReviewId.current;
    if (reviewId) {
      void api.cancelReview(project.id, reviewId).catch((error: unknown) => {
        onError(errorText(error));
      });
    }
    reviewAbort.current?.abort();
    reviewAbort.current = null;
    activeReviewId.current = null;
    setReviewing(false);
    setCancelled(true);
  };

  const requestReview = () => {
    const estimate = preview?.estimated_cost_usd ?? 0;
    const needsConfirmation = reviewMode !== "static" && config?.ui.confirm_expensive_reviews !== false && estimate >= (config?.budget.warn_above_usd ?? 0.25);
    if (needsConfirmation) setConfirming(true);
    else void runReview();
  };

  const overBudget = Boolean(
    reviewMode !== "static" && preview && config?.budget.max_spend_usd !== null && config?.budget.max_spend_usd !== undefined && preview.estimated_cost_usd > config.budget.max_spend_usd,
  );
  const aiProviderReady = Boolean(providerHealth && isUsable(providerHealth));
  const aiProviderBlocked = reviewMode !== "static" && !aiProviderReady;
  const providerMessage = providerChecking
    ? t("review.providerChecking")
    : providerHealth?.detail ??
      t("review.providerUnavailable");

  const updateFinding = async (reviewId: string, findingId: string, status: Finding["status"]) => {
    try {
      const updated = await api.updateFindingStatus(project.id, reviewId, findingId, status);
      setResult((current) => current ? { ...current, review: updated } : current);
      setHistory((current) => current.map((review) => review.id === updated.id ? updated : review));
    } catch (error) {
      onError(errorText(error));
    }
  };

  return (
    <>
      {!reviewing && !result && (
      <section className="mt-5 overflow-hidden rounded-panel border border-line bg-paper">
        <div className="flex flex-col justify-between gap-4 border-b border-line px-5 py-4 lg:flex-row lg:items-center">
          <div className="min-w-0">
            <p className="mb-0.5 flex items-center gap-2 text-[13.5px] font-semibold">
              <FolderGit2 className="size-4 text-low" strokeWidth={1.8} />
              <span className="truncate">{project.name}</span>
            </p>
            <p className="numeric truncate text-[10.5px] text-ink-subtle">
              {project.path}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <BranchSelect
              label="review.base"
              value={base}
              branches={project.branches}
              onChange={(value) => {
                if (reviewing) cancelReview();
                setResult(null);
                setBranchPreview(null);
                setBranchLoading(true);
                if (
                  reviewScope !== "branch_diff" &&
                  (reviewScope !== "selected_files" || selectedFiles.length > 0)
                ) {
                  setScopedLoading(true);
                }
                setFileQuery("");
                setEvents([]);
                setCancelled(false);
                setBase(value);
              }}
            />
            <GitCompareArrows className="mb-2 size-4 text-ink-subtle" />
            <BranchSelect
              label="review.head"
              value={head}
              branches={project.branches}
              onChange={(value) => {
                if (reviewing) cancelReview();
                setResult(null);
                setTree(null);
                setBranchPreview(null);
                setSelectedFiles([]);
                setTreeLoading(true);
                setBranchLoading(true);
                setScopedLoading(reviewScope === "whole_project");
                if (reviewScope === "selected_files") setScopedPreview(null);
                setFileQuery("");
                setHead(value);
                setEvents([]);
                setCancelled(false);
              }}
            />
            <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-subtle">
              {t("review.scope")}
              <select
                value={reviewScope}
                onChange={(event) => {
                  const scope = event.target.value as ReviewScope;
                  const nextSelectedFiles =
                    scope === "selected_files" && selectedFiles.length === 0
                      ? (tree?.files ?? [])
                      : selectedFiles;
                  setReviewScope(scope);
                  if (nextSelectedFiles !== selectedFiles) {
                    setSelectedFiles(nextSelectedFiles);
                  }
                  setFileUniverse(scope === "branch_diff" ? "changed" : "all");
                  setFileQuery("");
                  setScopedLoading(
                    scope === "whole_project" ||
                      (scope === "selected_files" && nextSelectedFiles.length > 0),
                  );
                  if (scope === "selected_files" && nextSelectedFiles.length === 0) {
                    setScopedPreview(null);
                  }
                  setResult(null);
                }}
                className="h-9 rounded-control border border-line-strong bg-paper px-2 text-[11.5px] font-medium normal-case tracking-normal text-ink outline-none"
              >
                <option value="branch_diff">{t("review.branchDiff")}</option>
                <option value="selected_files">{t("review.selectedFiles")}</option>
                <option value="whole_project">{t("review.wholeProject")}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-subtle">
              {t("review.reviewMode")}
              <select
                value={reviewMode}
                onChange={(event) => setReviewMode(event.target.value as ReviewMode)}
                disabled={reviewing}
                className="h-9 rounded-control border border-line-strong bg-paper px-2 text-[11.5px] font-medium normal-case tracking-normal text-ink outline-none focus:border-ink disabled:opacity-50"
              >
                <option value="static">{t("review.staticOnly")}</option>
                <option value="ai_assisted">{t("review.aiAssisted")}</option>
                <option value="both">{t("review.both")}</option>
              </select>
            </label>
            {reviewMode !== "static" && (
              <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-subtle">
                {t("review.scenario")}
                <select
                  value={scenarioId}
                  onChange={(event) => setScenarioId(event.target.value)}
                  disabled={reviewing}
                  className="h-9 max-w-[150px] rounded-control border border-line-strong bg-paper px-2 text-[11.5px] font-medium normal-case tracking-normal text-ink outline-none focus:border-ink disabled:opacity-50"
                >
                  <option value="">{t("review.scenarioDefault")}</option>
                  {scenarios.map((scenario) => (
                    <option key={scenario.id} value={scenario.id}>
                      {scenario.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading || reviewing}
              className="ml-1 flex h-9 items-center gap-2 rounded-control border border-line-strong px-3 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink disabled:opacity-50"
            >
              {loading ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <GitCompareArrows className="size-3.5" />
              )}
              {t("review.preview")}
            </button>
            <button
              type="button"
              onClick={reviewing ? cancelReview : requestReview}
              disabled={
                loading ||
                overBudget ||
                aiProviderBlocked ||
                (reviewScope === "selected_files" && selectedFiles.length === 0)
              }
              className="flex h-9 min-w-[112px] items-center justify-center gap-2 rounded-control bg-ink px-3.5 text-[11.5px] font-semibold text-paper hover:bg-ink-hover disabled:opacity-50"
            >
              {reviewing ? (
                <Square className="size-3.5 fill-current" />
              ) : (
                <ScanSearch className="size-3.5" />
              )}
              {t(reviewing ? "common.cancel" : result ? "review.runAgain" : reviewMode === "static" ? "review.runStatic" : reviewMode === "both" ? "review.runCombined" : "review.runAi")}
            </button>
          </div>
        </div>

        {aiProviderBlocked && (
          <div
            role="status"
            className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-medium-line bg-medium-surface px-5 py-2.5 text-[12px] text-medium"
          >
            <CircleAlert className="size-3.5 shrink-0" />
            <span className="min-w-0 flex-1">{providerMessage}</span>
            {!providerChecking && (
              <Link href="/settings/engine" className="font-semibold hover:underline">
                {t("review.openSettings")}
              </Link>
            )}
          </div>
        )}

        {analyzerPreflight && !analyzerPreflight.ready && reviewMode !== "ai_assisted" && (
          <div
            role="status"
            className="border-b border-medium-line bg-medium-surface px-5 py-2.5 text-[11.5px] text-medium"
          >
            {t("review.degradedCoverage", {
              analyzers: analyzerPreflight.analyzers
                .filter((item) => item.status !== "ready")
                .map((item) => item.name)
                .join(", "),
            })}
            <Link href="/settings/engine" className="ml-2 font-semibold hover:underline">
              {t("review.reviewSetup")}
            </Link>
          </div>
        )}

        <div className="grid min-h-[410px] lg:grid-cols-[330px_minmax(0,1fr)]">
          <ReviewFileBrowser
            trackedFiles={tree?.files ?? []}
            changedFiles={changedFiles}
            selectedFiles={selectedFiles}
            selectableMode={reviewScope === "selected_files"}
            universe={fileUniverse}
            layout={fileLayout}
            query={fileQuery}
            loadingTracked={treeLoading}
            loadingChanged={branchLoading}
            onUniverseChange={setFileUniverse}
            onLayoutChange={setFileLayout}
            onQueryChange={setFileQuery}
            onSelectionChange={(path, checked) => {
              const nextSelectedFiles = checked
                ? selectedFiles.includes(path)
                  ? selectedFiles
                  : [...selectedFiles, path]
                : selectedFiles.filter((item) => item !== path);
              setSelectedFiles(nextSelectedFiles);
              setScopedLoading(nextSelectedFiles.length > 0);
              if (nextSelectedFiles.length === 0) setScopedPreview(null);
            }}
          />

          <div className="min-w-0">
            <div className="flex min-h-11 flex-wrap items-center gap-x-5 gap-y-2 border-b border-line bg-sunken px-4 py-2">
              <Metric
                icon={<Code2 className="size-3" />}
                label={t("review.files")}
                value={String(preview?.files.length ?? 0)}
              />
              <Metric
                icon={<GitBranch className="size-3" />}
                label={t("review.lines")}
                value={
                  preview
                    ? `+${preview.additions} / -${preview.deletions}`
                    : "0"
                }
              />
              <Metric
                icon={<Boxes className="size-3" />}
                label={t("review.estTokens")}
                value={formatTokens(preview?.estimated_tokens ?? 0)}
              />
              <Metric
                icon={<CircleDollarSign className="size-3" />}
                label={t("review.estInput")}
                value={`$${(preview?.estimated_cost_usd ?? 0).toFixed(4)}`}
              />
            </div>
            <DiffViewer preview={preview} loading={loading} />
          </div>
        </div>
      </section>
      )}

      {(reviewing || events.length > 0 || result) && (
        <LiveReviewPanel
          result={result}
          events={events}
          running={reviewing}
          cancelled={cancelled}
          branches={{ base, head }}
          onFindingStatus={updateFinding}
        />
      )}
      {result && !reviewing && (
        <div className="mt-5 flex justify-end">
          <button
            type="button"
            onClick={() => {
              setResult(null);
              setEvents([]);
              setCancelled(false);
              void load();
            }}
            className="rounded-control border border-line-strong px-3 py-2 text-[12px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink"
          >
            {t("review.configureAnother")}
          </button>
        </div>
      )}
      <ReviewHistory
        reviews={history}
        onSelect={(review) => {
          setEvents([]);
          setCancelled(review.status === "aborted");
          setResult({
            review,
            stages: review.stages,
            analyzers: review.analyzers,
            chunks: [],
          });
        }}
      />
      {confirming && preview && (
        <CostConfirmation
          preview={preview}
          model={config?.engine.model ?? "configured model"}
          cap={config?.budget.max_spend_usd ?? null}
          onCancel={() => setConfirming(false)}
          onConfirm={() => { setConfirming(false); void runReview(); }}
        />
      )}
    </>
  );
}

/** Dedicated review route wrapper. Keeps review errors close to the action that caused them. */
export function ReviewSetupWorkspace({ project }: { project: Project }) {
  const toast = useToast();

  return (
    <>
      <ProjectQualityCommands project={project} onError={(message) => toast.push(message)} />
      <RepositoryInspector project={project} onError={(message) => toast.push(message)} />
    </>
  );
}


function ProjectQualityCommands({
  project,
  onError,
}: {
  project: Project;
  onError: (message: string) => void;
}) {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const [commands, setCommands] = useState({
    checkstyle_command: JSON.stringify(project.checkstyle_command),
    test_command: JSON.stringify(project.test_command),
    build_command: JSON.stringify(project.build_command),
  });
  const [baseBranch, setBaseBranch] = useState(project.base_branch);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    try {
      const parsed = Object.fromEntries(
        Object.entries(commands).map(([name, value]) => {
          const command = JSON.parse(value) as unknown;
          if (!Array.isArray(command) || !command.every((item) => typeof item === "string")) {
            throw new Error(`${name} must be a JSON array of command arguments.`);
          }
          return [name, command];
        }),
      );
      setSaving(true);
      await api.updateProject(project.id, { ...parsed, base_branch: baseBranch });
    } catch (error) {
      onError(errorText(error));
    } finally {
      setSaving(false);
    }
  };
  return (
    <details className="surface mb-4 px-4 py-3">
      <summary className="cursor-pointer text-[12px] font-semibold">
        {t("review.qualityCommands")}
        <span className="ml-2 font-normal text-ink-subtle">
          {t("review.qualityCommandsOptional")}
        </span>
      </summary>
      <p className="mt-2 text-[11px] text-ink-muted">
        {t("review.jsonArgumentArrays")}
        <code className="ml-1">[&quot;./mvnw&quot;,&quot;verify&quot;]</code>.
      </p>
      <div className="mt-3 grid gap-3 lg:grid-cols-4">
        <BranchSelect
          label="review.defaultBaseBranch"
          value={baseBranch}
          branches={project.branches}
          onChange={setBaseBranch}
          className="w-full"
        />
        {(
          [
            [
              "checkstyle_command",
              "review.checkstyle",
              "review.checkstyleDescription",
            ],
            [
              "test_command",
              "review.tests",
              "review.testsDescription",
            ],
            [
              "build_command",
              "review.build",
              "review.buildDescription",
            ],
          ] as const
        ).map(([name, label, description]) => (
          <div key={name} className="text-[10.5px] font-semibold text-ink-muted">
            <div className="flex items-center gap-1">
              <label htmlFor={`project-command-${name}`}>{t(label)}</label>
              <InfoTooltip label={`${t("review.moreInformationAbout")} ${t(label)}`}>
                {t(description)}
              </InfoTooltip>
            </div>
            <input
              id={`project-command-${name}`}
              value={commands[name]}
              onChange={(event) => setCommands((current) => ({
                ...current,
                [name]: event.target.value,
              }))}
              className="mt-1 h-9 w-full border border-line-strong bg-paper px-2 font-mono text-[10.5px] outline-none focus:border-ink"
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        disabled={saving}
        onClick={() => void save()}
        className="mt-3 bg-ink px-3 py-2 text-[11px] font-semibold text-paper disabled:opacity-50"
      >
        {saving ? t("review.saving") : t("review.saveProjectCommands")}
      </button>
    </details>
  );
}

const PIPELINE_STAGES = [
  "collect",
  "filter",
  "parse",
  "static",
  "chunk",
  "ai",
  "merge",
] as const;

function LiveReviewPanel({
  result,
  events,
  cancelled,
  running,
  branches,
  onFindingStatus,
}: {
  result: DeterministicReview | null;
  events: ReviewStreamEvent[];
  cancelled: boolean;
  running: boolean;
  branches: { base: string; head: string };
  onFindingStatus: (reviewId: string, findingId: string, status: Finding["status"]) => void;
}) {
  const { t } = useUiText();
  const review = result?.review;
  const reviewTitle = review?.mode === "static"
    ? t("review.staticReview")
    : review?.mode === "both"
      ? t("review.combinedReview")
      : t("review.aiReview");
  const stageEvents = events.filter(
    (event): event is Extract<ReviewStreamEvent, { type: "stage" }> =>
      event.type === "stage",
  );
  const completedStages = new Set([
    ...(result?.stages
      .filter((stage) => stage.status !== "failed")
      .map((stage) => stage.name) ?? []),
    ...stageEvents.map((event) => event.name),
  ]);
  const analyzers =
    result?.analyzers ??
    events.filter(
      (event): event is Extract<ReviewStreamEvent, { type: "analyzer" }> =>
        event.type === "analyzer",
    );
  const provider = [...events]
    .reverse()
    .find(
      (event): event is Extract<ReviewStreamEvent, { type: "provider" }> =>
        event.type === "provider",
    );
  const usage = [...events]
    .reverse()
    .find(
      (event): event is Extract<ReviewStreamEvent, { type: "usage" }> =>
        event.type === "usage",
    );
  const failure = events.find(
    (event): event is Extract<ReviewStreamEvent, { type: "failed" }> =>
      event.type === "failed",
  );
  const failed = Boolean(failure || review?.status === "failed");
  const errorText = useApiErrorText();
  const aborted = cancelled || review?.status === "aborted";
  const degraded = review?.status === "degraded";
  const tokens =
    (review?.stats.tokens_input ?? usage?.input_tokens ?? 0) +
    (review?.stats.tokens_output ?? usage?.output_tokens ?? 0);
  const cost = review?.stats.cost_usd ?? usage?.cost_usd ?? 0;
  const activeStage = Math.min(completedStages.size, PIPELINE_STAGES.length - 1);

  return (
    <section
      aria-label={reviewTitle}
      className="mt-4 overflow-hidden rounded-panel border border-line bg-paper"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h3 className="flex items-center gap-2 text-[14px] font-semibold">
            <Sparkles className="size-4 text-low" />
            {reviewTitle}
          </h3>
          <p className="mt-0.5 font-mono text-[10.5px] text-ink-subtle">
            {branches.base} → {branches.head}
            {` · ${provider?.model ?? review?.effective_model ?? review?.model ?? "local"}`}
          </p>
        </div>
        <span
          className={`flex items-center gap-1.5 rounded-control border px-2.5 py-1 text-[10.5px] font-semibold ${
            failed
              ? "border-critical-line bg-critical-surface text-critical"
              : aborted || degraded
                ? "border-medium-line bg-medium-surface text-medium"
                : running
                  ? "border-low-line bg-low-surface text-low"
                  : "border-success-line bg-success-surface text-success"
          }`}
        >
          {failed || aborted || degraded ? (
            <CircleX className="size-3.5" />
          ) : running ? (
            <LoaderCircle className="size-3.5 animate-spin" />
          ) : (
            <CircleCheck className="size-3.5" />
          )}
          {failed
            ? t("review.status.failed")
            : aborted
              ? t("review.status.cancelled")
              : degraded
                ? t("review.status.degraded")
              : running
                ? t("review.status.reviewing")
                : tokens
                  ? t("review.status.completedTokens", { tokens: formatTokens(tokens) })
                  : t("review.status.completed")}
        </span>
      </div>

      <div className="grid grid-cols-2 border-b border-line bg-sunken sm:grid-cols-5">
        <ReviewMetric label={t("review.metric.findings")} value={review ? String(review.findings.length) : "—"} />
        <ReviewMetric
          label={t("review.metric.filesReviewed")}
          value={review ? String(review.stats.files_analysed) : "—"}
        />
        <ReviewMetric
          label={tokens ? t("review.metric.tokens") : t("review.metric.estContext")}
          value={tokens ? formatTokens(tokens) : review ? `~${formatTokens(review.stats.estimated_context_tokens)}` : "—"}
        />
        <ReviewMetric
          label={review?.stats.cost_is_estimated || usage?.is_estimated ? t("review.metric.estCost") : t("review.metric.cost")}
          value={usage || review ? `$${cost.toFixed(4)}` : "—"}
        />
        <ReviewMetric
          label={t("review.metric.duration")}
          value={review ? `${review.stats.duration_ms} ms` : t("review.metric.live")}
        />
      </div>

      <div className="border-b border-line px-5 py-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
          {PIPELINE_STAGES.map((name, index) => {
            const completed = completedStages.has(name);
            const active = running && !completed && index === activeStage;
            const detail =
              result?.stages.find((stage) => stage.name === name)?.detail ??
              stageEvents.find((stage) => stage.name === name)?.detail;
            return (
              <div
                key={name}
                className={`flex min-w-0 items-center gap-2 rounded-control border px-2.5 py-2 ${
                  completed
                    ? "border-success-line bg-success-surface"
                    : active
                      ? "border-low-line bg-low-surface"
                      : "border-line"
                }`}
                title={detail ?? undefined}
              >
                <span
                  className={`grid size-5 shrink-0 place-items-center rounded-full font-mono text-[9px] font-semibold ${
                    completed
                      ? "bg-paper text-success"
                      : active
                        ? "bg-paper text-low"
                        : "bg-canvas text-ink-subtle"
                  }`}
                >
                  {completed ? <Check className="size-3" /> : index + 1}
                </span>
                <span className="truncate text-[10.5px] font-semibold capitalize">
                  {name}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-b border-line lg:border-b-0 lg:border-r">
          <div className="border-b border-line p-4">
            <h4 className="mb-2.5 flex items-center gap-2 text-[11px] font-semibold uppercase text-ink-subtle">
              <Activity className="size-3.5" />
              {t("review.eventStream")}
            </h4>
            <div className="max-h-48 space-y-0.5 overflow-auto">
              {events.length ? (
                events.slice(-10).map((event, index) => (
                  <ReviewEventRow key={`${event.type}-${index}`} event={event} />
                ))
              ) : (
                <p className="px-2 py-3 text-[10.5px] text-ink-subtle">
                  {review
                    ? t("review.event.persisted", { count: review.events.length, status: t(`status.${review.status}`) })
                    : t("review.startingAnalysis")}
                </p>
              )}
            </div>
          </div>
          <div className="p-4">
            <h4 className="mb-2.5 text-[11px] font-semibold uppercase text-ink-subtle">
              {t("review.analyzers")}
            </h4>
            <div className="space-y-1">
              {analyzers.length ? (
                analyzers.map((analyzer) => (
                  <AnalyzerRow key={analyzer.name} analyzer={analyzer} />
                ))
              ) : (
                <p className="px-2 py-2 text-[10.5px] text-ink-subtle">{t("review.analyzersPending")}</p>
              )}
            </div>
          </div>
        </aside>

        <div className="min-w-0">
          <div className="flex h-11 items-center justify-between border-b border-line bg-sunken px-4">
            <h4 className="flex items-center gap-2 text-[11.5px] font-semibold">
              <CircleAlert className="size-3.5 text-ink-subtle" />
              {t("review.metric.findings")}
            </h4>
            <span className="font-mono text-[10.5px] text-ink-subtle">
              {review?.findings.length ?? 0}
            </span>
          </div>
          {review?.findings.length ? (
            <div className="divide-y divide-line">
              {review.findings.map((finding) => (
                <FindingCard
                  key={finding.id}
                  finding={finding}
                  onStatus={(status) => onFindingStatus(review.id, finding.id, status)}
                />
              ))}
            </div>
          ) : running ? (
            <div className="grid min-h-52 place-items-center px-5 py-8 text-center">
              <div>
                <LoaderCircle className="mx-auto mb-2.5 size-6 animate-spin text-low" />
                <p className="text-[12.5px] font-semibold">{t("review.inProgress")}</p>
                <p className="mt-1 text-[11px] text-ink-muted">
                  {provider ? t("review.validatingStreamed") : t("review.runningLocalAnalyzers")}
                </p>
              </div>
            </div>
          ) : (
            <div className="grid min-h-52 place-items-center px-5 py-8 text-center">
              <div>
                {failed || aborted ? (
                  <CircleX
                    className={`mx-auto mb-2.5 size-6 ${failed ? "text-critical" : "text-medium"}`}
                  />
                ) : (
                  <CircleCheck className="mx-auto mb-2.5 size-6 text-success" />
                )}
                <p className="text-[12.5px] font-semibold">
                  {failed ? t("review.stopped") : aborted ? t("review.status.cancelled") : t("review.noFindings")}
                </p>
                <p className="mt-1 text-[11px] text-ink-muted">
                  {(failure
                    ? errorText({ message: failure.error_key, errorKey: failure.error_key, params: failure.params })
                    : null) ??
                    review?.error ??
                    (aborted ? t("review.jobCancelled") : t("review.noIssuesReported"))}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ReviewEventRow({ event }: { event: ReviewStreamEvent }) {
  const { t } = useUiText();
  let label: string;
  switch (event.type) {
    case "review_queued":
      label = t("review.event.queued");
      break;
    case "review_started":
      label = t("review.event.started");
      break;
    case "stage":
      label = `${event.name} · ${event.duration_ms} ms`;
      break;
    case "analyzer":
      label = `${event.name} · ${t("review.event.findings", { count: event.findings })}`;
      break;
    case "provider":
      label = t("review.event.model", { model: event.model });
      break;
    case "delta":
      label = t("review.event.delta", { chars: event.characters });
      break;
    case "retry":
      label = t("review.event.retry", { attempt: event.attempt, message: event.message });
      break;
    case "usage":
      label = t("review.event.usage", { tokens: formatTokens(event.input_tokens + event.output_tokens) });
      break;
    case "completed":
      label = t("review.event.completed");
      break;
    case "failed":
      label = event.error_key;
      break;
    case "aborted":
      label = t("review.event.cancelled");
      break;
  }
  return (
    <div className="flex items-center gap-2 rounded-chip px-2 py-1.5 text-[10.5px]">
      <span className="size-1.5 shrink-0 rounded-full bg-low" />
      <span className="min-w-0 truncate text-ink-muted">{label}</span>
    </div>
  );
}

function ReviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-line px-4 py-3 last:border-r-0">
      <p className="font-mono text-[14px] font-semibold">{value}</p>
      <p className="mt-0.5 text-[9.5px] font-semibold uppercase text-ink-subtle">
        {label}
      </p>
    </div>
  );
}

function AnalyzerRow({ analyzer }: { analyzer: AnalyzerRun }) {
  const Icon =
    analyzer.status === "completed"
      ? CircleCheck
      : analyzer.status === "failed"
        ? CircleX
        : CircleAlert;
  const tone =
    analyzer.status === "completed"
      ? "text-success"
      : analyzer.status === "failed"
        ? "text-critical"
        : analyzer.status === "degraded"
          ? "text-medium"
          : "text-ink-subtle";
  return (
    <div
      className="flex items-center gap-2 rounded-control px-2 py-2 hover:bg-canvas"
      title={analyzer.detail ?? undefined}
    >
      <Icon className={`size-3.5 shrink-0 ${tone}`} />
      <span className="min-w-0 flex-1 truncate text-[11px] font-medium capitalize">
        {analyzer.name}
      </span>
      <span className="font-mono text-[10px] text-ink-subtle">
        {analyzer.status === "completed" || analyzer.status === "degraded"
          ? analyzer.findings
          : "—"}
      </span>
    </div>
  );
}

function ReviewHistory({ reviews, onSelect }: { reviews: Review[]; onSelect: (review: Review) => void }) {
  const { t } = useUiText();
  if (!reviews.length) return null;
  return (
    <section className="mt-4 overflow-hidden rounded-panel border border-line bg-paper" aria-label={t("review.history")}>
      <div className="flex items-center justify-between border-b border-line bg-sunken px-4 py-3">
        <h3 className="text-[12px] font-semibold">{t("review.history")}</h3>
        <span className="font-mono text-[10.5px] text-ink-subtle">{reviews.length}</span>
      </div>
      <div className="divide-y divide-line">
        {reviews.slice(0, 8).map((review) => (
          <button key={review.id} type="button" onClick={() => onSelect(review)} className="grid w-full grid-cols-[1fr_auto] gap-3 px-4 py-3 text-left hover:bg-canvas">
            <span className="min-w-0"><span className="block truncate text-[11.5px] font-semibold">{review.base_branch} → {review.head_branch}</span><span className="block text-[10.5px] text-ink-subtle">{relativeDate(review.created_at, new Date().toISOString(), t)} · {review.model ?? t("review.localAnalysis")}</span></span>
            <span className="text-[10.5px] text-ink-muted">{t("review.historyFindings", { count: review.findings.length })} · ${review.stats.cost_usd.toFixed(4)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function CostConfirmation({ preview, model, cap, onCancel, onConfirm }: { preview: DiffPreview; model: string; cap: number | null; onCancel: () => void; onConfirm: () => void }) {
  const { t } = useUiText();
  return (
    <div role="presentation" className="fixed inset-0 z-50 grid place-items-center bg-black/25 p-4">
      <section role="dialog" aria-modal="true" aria-labelledby="cost-confirmation-title" className="w-full max-w-[440px] border border-line bg-paper shadow-2xl">
        <div className="border-b border-line px-5 py-4"><h2 id="cost-confirmation-title" className="text-[15px] font-semibold">{t("review.cost.title")}</h2><p className="mt-1 text-[12px] text-ink-muted">{t("review.cost.exceedsThreshold")}</p></div>
        <div className="space-y-2 px-5 py-4 text-[12px] text-ink-muted"><p><strong className="text-ink">{t("review.cost.model")}</strong> {model}</p><p><strong className="text-ink">{t("review.cost.scope")}</strong> {t("review.cost.scopeDetail", { count: preview.files.length, tokens: formatTokens(preview.estimated_tokens) })}</p><p><strong className="text-ink">{t("review.cost.estimatedInput")}</strong> ${preview.estimated_cost_usd.toFixed(4)}{cap !== null ? t("review.cost.budgetSuffix", { cap: `$${cap.toFixed(2)}` }) : ""}</p></div>
        <div className="flex justify-end gap-2 border-t border-line px-5 py-4"><button type="button" onClick={onCancel} className="border border-line-strong px-3 py-2 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas">{t("common.cancel")}</button><button type="button" onClick={onConfirm} className="bg-ink px-3 py-2 text-[11.5px] font-semibold text-paper hover:bg-ink-hover">{t("review.cost.runReview")}</button></div>
      </section>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: ReactElement;
  label: string;
  value: string;
}) {
  return (
    <span className="flex items-center gap-1.5 text-[10.5px] text-ink-subtle">
      {icon}
      <span>{label}</span>
      <strong className="numeric font-medium text-ink-muted">{value}</strong>
    </span>
  );
}

