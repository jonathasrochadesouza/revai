"use client";

import {
  Activity,
  ArrowRight,
  Boxes,
  Check,
  CircleAlert,
  CircleCheck,
  CircleDollarSign,
  CircleX,
  ClipboardCheck,
  Code2,
  Copy,
  File,
  Files,
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

import {
  ApiError,
  api,
  type AnalyzerRun,
  type DeterministicReview,
  type DiffPreview,
  type Finding,
  type Project,
  type ProjectTree,
  type Review,
  type ReviewStreamEvent,
  type RevaiConfig,
  type Severity,
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

function relativeDate(value: string, renderedAt: string): string {
  const elapsed = new Date(renderedAt).getTime() - new Date(value).getTime();
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatTokens(tokens: number): string {
  if (tokens < 1_000) return String(tokens);
  return `${(tokens / 1_000).toFixed(tokens < 10_000 ? 1 : 0)}k`;
}

function displayError(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong while talking to the local API.";
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
  const [projects, setProjects] = useState(initialProjects);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ProjectFilter>("all");
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [notice, setNotice] = useState<string | null>(initialError ?? null);
  const searchRef = useRef<HTMLInputElement>(null);

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
            Projects
          </h1>
          <p className="max-w-[64ch] text-[14px] leading-relaxed text-ink-muted">
            Repository access stays local. Only filtered review context reaches
            the provider you configure.
          </p>
        </div>
        <label className="flex h-10 w-full items-center gap-2.5 rounded-control border border-line-strong bg-paper px-3 text-ink-subtle lg:w-[310px]">
          <Search aria-hidden className="size-4 shrink-0" strokeWidth={1.8} />
          <span className="sr-only">Search projects</span>
          <input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search projects"
            className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-subtle"
          />
          <kbd className="rounded-chip border border-line px-1.5 py-0.5 text-[10px]">
            Ctrl K
          </kbd>
        </label>
      </section>

      {notice && (
        <div
          role="status"
          className="mb-5 flex items-start gap-3 rounded-control border border-critical-line bg-critical-surface px-4 py-3 text-[12.5px] text-critical"
        >
          <span className="flex-1">{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Dismiss message"
            className="rounded-chip p-0.5 hover:bg-paper"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}

      <OnboardingChecklist hasProjects={projects.length > 0} />

      <section aria-label="Add a repository" className="mb-8 grid gap-3 md:grid-cols-2">
        <EntryAction
          icon={<HardDrive className="size-5" strokeWidth={1.8} />}
          title="Open local folder"
          description="Point RevAI at a Git repository already on this machine."
          action="Browse or enter path"
          onClick={() => setDialog("open")}
        />
        <EntryAction
          icon={<Copy className="size-5" strokeWidth={1.8} />}
          title="Clone from remote"
          description="Clone an HTTPS, SSH, or local Git remote into a folder you choose."
          action="Choose URL and folder"
          onClick={() => setDialog("clone")}
        />
      </section>

      <section className="surface overflow-hidden">
        <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h2 className="flex items-center gap-2 text-[14px] font-semibold">
            Your projects
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
                className={`rounded-chip px-3 py-1.5 text-[11.5px] font-medium capitalize transition-colors ${
                  filter === value
                    ? "border border-line bg-paper text-ink"
                    : "border border-transparent text-ink-subtle hover:text-ink"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        <div className="hidden grid-cols-[minmax(260px,1fr)_180px_170px_90px] gap-4 border-b border-line bg-sunken px-5 py-2.5 text-[10px] font-semibold uppercase text-ink-subtle md:grid">
          <span>Repository</span>
          <span>Branch</span>
          <span>Languages</span>
          <span className="text-right">Added</span>
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
                {project.languages.join(", ") || "Not detected"}
              </span>
              <span className="numeric text-[11px] text-ink-subtle md:text-right">
                {relativeDate(project.created_at, renderedAt)}
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
            setNotice(null);
            try {
              await refresh();
            } catch (error) {
              setNotice(displayError(error));
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
  return (
    <div className="grid min-h-48 place-items-center px-5 py-10 text-center">
      <div>
        <FolderGit2 className="mx-auto mb-3 size-7 text-ink-subtle" strokeWidth={1.5} />
        <p className="mb-1 text-[13px] font-semibold">
          {hasProjects ? "No projects match this view" : "No repositories yet"}
        </p>
        <p className="mb-4 text-[12px] text-ink-muted">
          {hasProjects
            ? "Try a different search or project filter."
            : "Open a local Git folder to start inspecting changes."}
        </p>
        {!hasProjects && (
          <button
            type="button"
            onClick={onOpen}
            className="rounded-control bg-ink px-3.5 py-2 text-[11.5px] font-semibold text-white hover:bg-zinc-800"
          >
            Open repository
          </button>
        )}
      </div>
    </div>
  );
}

function OnboardingChecklist({ hasProjects }: { hasProjects: boolean }) {
  const [config, setConfig] = useState<RevaiConfig | null>(null);
  const [providerReady, setProviderReady] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getConfig(), api.getProviders()]).then(([saved, providers]) => {
      if (!active) return;
      setConfig(saved.config);
      setProviderReady(providers.active_is_usable);
    }).catch(() => {
      if (active) setProviderReady(false);
    });
    return () => { active = false; };
  }, []);

  const steps = [
    { label: "Configure an engine", done: Boolean(config?.engine.model), href: "/settings/engine" },
    { label: "Verify provider access", done: providerReady === true, href: "/settings/engine" },
    { label: "Add a repository", done: hasProjects, href: "#repositories" },
  ];
  if (steps.every((step) => step.done)) return null;
  return (
    <section className="mb-6 border border-line bg-paper px-5 py-4" aria-label="Getting started">
      <div className="mb-3 flex items-center gap-2">
        <ClipboardCheck className="size-4 text-low" />
        <h2 className="text-[13px] font-semibold">Get ready for your first review</h2>
      </div>
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
  const [value, setValue] = useState("");
  const [destination, setDestination] = useState("");
  const [pending, setPending] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!value.trim() || (mode === "clone" && !destination.trim())) return;
    setPending(true);
    setError(null);
    try {
      const project =
        mode === "open"
          ? await api.openProject(value.trim())
          : await api.cloneProject(value.trim(), destination.trim());
      onCreated(project);
    } catch (cause) {
      setError(displayError(cause));
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
    setError(null);
    try {
      const result = await api.pickProjectFolder();
      if (result.path) {
        if (isOpen) setValue(result.path);
        else setDestination(result.path);
      }
    } catch (cause) {
      setError(displayError(cause));
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
              {isOpen ? "Open local folder" : "Clone from remote"}
            </h2>
            <p className="mt-1 text-[12px] text-ink-muted">
              {isOpen
                ? "Browse for a Git repository or enter its absolute path."
                : "Choose a remote repository and where to save its local checkout."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close dialog"
            className="rounded-control p-1.5 text-ink-subtle hover:bg-canvas hover:text-ink disabled:opacity-40"
          >
            <X className="size-4" />
          </button>
        </div>
        <form onSubmit={submit} className="p-5">
          <label className="mb-1.5 block text-[11.5px] font-semibold" htmlFor="repository-source">
            {isOpen ? "Folder path" : "Repository URL"}
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
                {browsing ? "Selecting" : "Browse"}
              </button>
            )}
          </div>
          {!isOpen && (
            <>
              <label
                className="mb-1.5 mt-4 block text-[11.5px] font-semibold"
                htmlFor="repository-destination"
              >
                Save in
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
                  {browsing ? "Selecting" : "Browse"}
                </button>
              </div>
            </>
          )}
          {error && (
            <p role="alert" className="mt-2 text-[11.5px] text-critical">
              {error}
            </p>
          )}
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded-control border border-line-strong px-3.5 py-2 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !canSubmit}
              className="flex min-w-[88px] items-center justify-center gap-2 rounded-control bg-ink px-3.5 py-2 text-[11.5px] font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending && <LoaderCircle className="size-3.5 animate-spin" />}
              {pending ? (isOpen ? "Opening" : "Cloning") : isOpen ? "Open" : "Clone"}
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
  const defaultHead = project.current_branch ?? project.base_branch;
  const [base, setBase] = useState(project.base_branch);
  const [head, setHead] = useState(defaultHead);
  const [tree, setTree] = useState<ProjectTree | null>(null);
  const [preview, setPreview] = useState<DiffPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [result, setResult] = useState<DeterministicReview | null>(null);
  const [cancelled, setCancelled] = useState(false);
  const [events, setEvents] = useState<ReviewStreamEvent[]>([]);
  const [config, setConfig] = useState<RevaiConfig | null>(null);
  const [history, setHistory] = useState<Review[]>([]);
  const [confirming, setConfirming] = useState(false);
  const reviewAbort = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => reviewAbort.current?.abort();
  }, []);

  const fetchData = useCallback(
    () =>
      Promise.all([
        api.getProjectTree(project.id, head),
        api.getProjectDiff(project.id, base, head),
      ]),
    [base, head, project.id],
  );

  const load = useCallback(async () => {
    try {
      const [nextTree, nextPreview] = await fetchData();
      setTree(nextTree);
      setPreview(nextPreview);
    } catch (error) {
      onError(displayError(error));
    } finally {
      setLoading(false);
    }
  }, [fetchData, onError]);

  const loadHistory = useCallback(async () => {
    try {
      const response = await api.getProjectReviews(project.id);
      setHistory(response.reviews);
    } catch (error) {
      onError(displayError(error));
    }
  }, [onError, project.id]);

  useEffect(() => {
    void loadHistory();
    api.getConfig().then((response) => setConfig(response.config)).catch(() => undefined);
  }, [loadHistory]);

  useEffect(() => {
    let active = true;
    void fetchData()
      .then(([nextTree, nextPreview]) => {
        if (!active) return;
        setTree(nextTree);
        setPreview(nextPreview);
      })
      .catch((error: unknown) => {
        if (active) onError(displayError(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [fetchData, onError]);

  const runReview = async () => {
    const controller = new AbortController();
    reviewAbort.current?.abort();
    setCancelled(false);
    reviewAbort.current = controller;
    setReviewing(true);
    setResult(null);
    setEvents([]);
    try {
      const nextResult = await api.streamReview(project.id, base, head, {
        signal: controller.signal,
        onEvent: (event) => {
          setEvents((current) => {
            const last = current.at(-1);
            if (event.type === "delta" && last?.type === "delta") {
              return [...current.slice(0, -1), event];
            }
            return [...current, event].slice(-80);
          });
        },
      });
      setResult(nextResult);
      void loadHistory();
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        onError(displayError(error));
      }
    } finally {
      if (reviewAbort.current === controller) {
        reviewAbort.current = null;
        setReviewing(false);
      }
    }
  };

  const cancelReview = () => {
    reviewAbort.current?.abort();
    reviewAbort.current = null;
    setReviewing(false);
    setCancelled(true);
  };

  const requestReview = () => {
    const estimate = preview?.estimated_cost_usd ?? 0;
    const needsConfirmation = config?.ui.confirm_expensive_reviews !== false && estimate >= (config?.budget.warn_above_usd ?? 0.25);
    if (needsConfirmation) setConfirming(true);
    else void runReview();
  };

  const overBudget = Boolean(
    preview && config?.budget.max_spend_usd !== null && config?.budget.max_spend_usd !== undefined && preview.estimated_cost_usd > config.budget.max_spend_usd,
  );

  const updateFinding = async (reviewId: string, findingId: string, status: Finding["status"]) => {
    try {
      const updated = await api.updateFindingStatus(project.id, reviewId, findingId, status);
      setResult((current) => current ? { ...current, review: updated } : current);
      setHistory((current) => current.map((review) => review.id === updated.id ? updated : review));
    } catch (error) {
      onError(displayError(error));
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
              label="Base"
              value={base}
              branches={project.branches}
              onChange={(value) => {
                if (reviewing) cancelReview();
                setResult(null);
                setLoading(true);
                setEvents([]);
                setCancelled(false);
                setBase(value);
              }}
            />
            <GitCompareArrows className="mb-2 size-4 text-ink-subtle" />
            <BranchSelect
              label="Head"
              value={head}
              branches={project.branches}
              onChange={(value) => {
                if (reviewing) cancelReview();
                setResult(null);
                setLoading(true);
                setHead(value);
                setEvents([]);
                setCancelled(false);
              }}
            />
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                void load();
              }}
              disabled={loading || reviewing}
              className="ml-1 flex h-9 items-center gap-2 rounded-control border border-line-strong px-3 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink disabled:opacity-50"
            >
              {loading ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <GitCompareArrows className="size-3.5" />
              )}
              Preview
            </button>
            <button
              type="button"
              onClick={reviewing ? cancelReview : requestReview}
              disabled={loading || overBudget}
              className="flex h-9 min-w-[112px] items-center justify-center gap-2 rounded-control bg-ink px-3.5 text-[11.5px] font-semibold text-white hover:bg-zinc-800 disabled:opacity-50"
            >
              {reviewing ? (
                <Square className="size-3.5 fill-current" />
              ) : (
                <ScanSearch className="size-3.5" />
              )}
              {reviewing ? "Cancel" : result ? "Run again" : "Run AI review"}
            </button>
          </div>
        </div>

        <div className="grid min-h-[410px] lg:grid-cols-[270px_minmax(0,1fr)]">
          <aside className="border-b border-line lg:border-b-0 lg:border-r">
            <div className="flex h-11 items-center justify-between border-b border-line bg-sunken px-4">
              <h3 className="flex items-center gap-2 text-[11.5px] font-semibold">
                <Files className="size-3.5 text-ink-subtle" />
                Tracked files
              </h3>
              <span className="numeric text-[10.5px] text-ink-subtle">
                {tree?.files.length ?? 0}
              </span>
            </div>
            <div className="max-h-[360px] overflow-auto p-2">
              {loading && !tree ? (
                <LoadingRows />
              ) : tree?.files.length ? (
                tree.files.map((path) => (
                  <div
                    key={path}
                    className="flex min-w-0 items-center gap-2 rounded-chip px-2 py-1.5 text-[11px] text-ink-muted hover:bg-canvas"
                    title={path}
                  >
                    <File className="size-3.5 shrink-0 text-ink-subtle" strokeWidth={1.7} />
                    <span className="truncate font-mono">{path}</span>
                  </div>
                ))
              ) : (
                <p className="px-2 py-3 text-[11px] text-ink-subtle">No tracked files.</p>
              )}
            </div>
          </aside>

          <div className="min-w-0">
            <div className="flex min-h-11 flex-wrap items-center gap-x-5 gap-y-2 border-b border-line bg-sunken px-4 py-2">
              <Metric
                icon={<Code2 className="size-3" />}
                label="Files"
                value={String(preview?.files.length ?? 0)}
              />
              <Metric
                icon={<GitBranch className="size-3" />}
                label="Lines"
                value={
                  preview
                    ? `+${preview.additions} / -${preview.deletions}`
                    : "0"
                }
              />
              <Metric
                icon={<Boxes className="size-3" />}
                label="Est. tokens"
                value={formatTokens(preview?.estimated_tokens ?? 0)}
              />
              <Metric
                icon={<CircleDollarSign className="size-3" />}
                label="Est. input"
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
              setLoading(true);
              void load();
            }}
            className="rounded-control border border-line-strong px-3 py-2 text-[12px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink"
          >
            Configure another review
          </button>
        </div>
      )}
      <ReviewHistory reviews={history} onSelect={(review) => setResult({ review, stages: [], analyzers: [], chunks: [] })} />
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
  const [notice, setNotice] = useState<string | null>(null);

  return (
    <>
      {notice && (
        <div
          role="status"
          className="mb-5 flex items-start gap-3 rounded-control border border-critical-line bg-critical-surface px-4 py-3 text-[12.5px] text-critical"
        >
          <span className="flex-1">{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Dismiss message"
            className="rounded-chip p-0.5 hover:bg-paper"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
      <RepositoryInspector project={project} onError={setNotice} />
    </>
  );
}

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "border-critical-line bg-critical-surface text-critical",
  medium: "border-medium-line bg-medium-surface text-medium",
  low: "border-low-line bg-low-surface text-low",
};

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
  const review = result?.review;
  const stageEvents = events.filter(
    (event): event is Extract<ReviewStreamEvent, { type: "stage" }> =>
      event.type === "stage",
  );
  const completedStages = new Set(stageEvents.map((event) => event.name));
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
  const tokens =
    (review?.stats.tokens_input ?? usage?.input_tokens ?? 0) +
    (review?.stats.tokens_output ?? usage?.output_tokens ?? 0);
  const cost = review?.stats.cost_usd ?? usage?.cost_usd ?? 0;
  const activeStage = Math.min(completedStages.size, PIPELINE_STAGES.length - 1);

  return (
    <section
      aria-label="Live AI review"
      className="mt-4 overflow-hidden rounded-panel border border-line bg-paper"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h3 className="flex items-center gap-2 text-[14px] font-semibold">
            <Sparkles className="size-4 text-low" />
            AI review
          </h3>
          <p className="mt-0.5 font-mono text-[10.5px] text-ink-subtle">
            {branches.base} → {branches.head}
            {provider ? ` · ${provider.model}` : ""}
          </p>
        </div>
        <span
          className={`flex items-center gap-1.5 rounded-control border px-2.5 py-1 text-[10.5px] font-semibold ${
            failure
              ? "border-critical-line bg-critical-surface text-critical"
              : cancelled
                ? "border-medium-line bg-medium-surface text-medium"
                : running
                  ? "border-low-line bg-low-surface text-low"
                  : "border-success-line bg-success-surface text-success"
          }`}
        >
          {failure || cancelled ? (
            <CircleX className="size-3.5" />
          ) : running ? (
            <LoaderCircle className="size-3.5 animate-spin" />
          ) : (
            <CircleCheck className="size-3.5" />
          )}
          {failure
            ? "Failed"
            : cancelled
              ? "Cancelled"
              : running
                ? "Reviewing"
                : `Completed · ${formatTokens(tokens)} tokens`}
        </span>
      </div>

      <div className="grid grid-cols-2 border-b border-line bg-sunken sm:grid-cols-5">
        <ReviewMetric label="Findings" value={review ? String(review.findings.length) : "—"} />
        <ReviewMetric
          label="Files checked"
          value={review ? String(review.stats.files_analysed) : "—"}
        />
        <ReviewMetric label="Tokens" value={tokens ? formatTokens(tokens) : "—"} />
        <ReviewMetric label="Cost" value={usage || review ? `$${cost.toFixed(4)}` : "—"} />
        <ReviewMetric
          label="Duration"
          value={review ? `${review.stats.duration_ms} ms` : "Live"}
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
              Event stream
            </h4>
            <div className="max-h-48 space-y-0.5 overflow-auto">
              {events.length ? (
                events.slice(-10).map((event, index) => (
                  <ReviewEventRow key={`${event.type}-${index}`} event={event} />
                ))
              ) : (
                <p className="px-2 py-3 text-[10.5px] text-ink-subtle">
                  Starting local analysis…
                </p>
              )}
            </div>
          </div>
          <div className="p-4">
            <h4 className="mb-2.5 text-[11px] font-semibold uppercase text-ink-subtle">
              Analyzers
            </h4>
            <div className="space-y-1">
              {analyzers.length ? (
                analyzers.map((analyzer) => (
                  <AnalyzerRow key={analyzer.name} analyzer={analyzer} />
                ))
              ) : (
                <p className="px-2 py-2 text-[10.5px] text-ink-subtle">Pending</p>
              )}
            </div>
          </div>
        </aside>

        <div className="min-w-0">
          <div className="flex h-11 items-center justify-between border-b border-line bg-sunken px-4">
            <h4 className="flex items-center gap-2 text-[11.5px] font-semibold">
              <CircleAlert className="size-3.5 text-ink-subtle" />
              Findings
            </h4>
            <span className="font-mono text-[10.5px] text-ink-subtle">
              {review?.findings.length ?? 0}
            </span>
          </div>
          {review?.findings.length ? (
            <div className="divide-y divide-line">
              {review.findings.map((finding) => (
                <FindingRow
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
                <p className="text-[12.5px] font-semibold">Review in progress</p>
                <p className="mt-1 text-[11px] text-ink-muted">
                  {provider ? "Validating streamed findings" : "Running local analyzers"}
                </p>
              </div>
            </div>
          ) : (
            <div className="grid min-h-52 place-items-center px-5 py-8 text-center">
              <div>
                {failure || cancelled ? (
                  <CircleX
                    className={`mx-auto mb-2.5 size-6 ${failure ? "text-critical" : "text-medium"}`}
                  />
                ) : (
                  <CircleCheck className="mx-auto mb-2.5 size-6 text-success" />
                )}
                <p className="text-[12.5px] font-semibold">
                  {failure ? "Review stopped" : cancelled ? "Review cancelled" : "No findings"}
                </p>
                <p className="mt-1 text-[11px] text-ink-muted">
                  {failure?.message ?? (cancelled ? "No findings were persisted." : "Local analyzers and AI reported no issues.")}
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
  let label: string;
  switch (event.type) {
    case "review_queued":
      label = "Queued — waiting for a review slot";
      break;
    case "review_started":
      label = "Review started";
      break;
    case "stage":
      label = `${event.name} · ${event.duration_ms} ms`;
      break;
    case "analyzer":
      label = `${event.name} · ${event.findings} findings`;
      break;
    case "provider":
      label = `Model · ${event.model}`;
      break;
    case "delta":
      label = `Model output · ${event.characters} chars`;
      break;
    case "retry":
      label = `Retry ${event.attempt} · ${event.message}`;
      break;
    case "usage":
      label = `Usage · ${formatTokens(event.input_tokens + event.output_tokens)} tokens`;
      break;
    case "completed":
      label = "Review completed";
      break;
    case "failed":
      label = event.message;
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
        {analyzer.status === "completed" ? analyzer.findings : "—"}
      </span>
    </div>
  );
}

function FindingRow({
  finding,
  onStatus,
}: {
  finding: Finding;
  onStatus: (status: Finding["status"]) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const copyPatch = async () => {
    if (!finding.suggested_patch) return;
    await navigator.clipboard.writeText(finding.suggested_patch);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };
  return (
    <article className="px-4 py-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-chip border px-2 py-0.5 text-[9.5px] font-semibold capitalize ${SEVERITY_STYLES[finding.severity]}`}
        >
          {finding.severity}
        </span>
        <span className="font-mono text-[10px] text-ink-subtle">
          {finding.file}:{finding.line_start}
        </span>
        <span className="text-[9.5px] font-semibold uppercase text-ink-subtle">{finding.source}</span>
        <span className="ml-auto text-[9.5px] font-semibold capitalize text-ink-subtle">{finding.status.replace("_", " ")}</span>
      </div>
      <h5 className="text-[12.5px] font-semibold leading-snug">{finding.title}</h5>
      <p className="mt-1 text-[11.5px] leading-relaxed text-ink-muted">{finding.description}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setExpanded((value) => !value)} className="text-[10.5px] font-semibold text-low hover:underline">
          {expanded ? "Hide evidence" : "Why this matters"}
        </button>
        <span className="text-[10.5px] text-ink-subtle">Confidence {Math.round(finding.confidence * 100)}%</span>
        {finding.suggested_patch && <button type="button" onClick={() => void copyPatch()} className="text-[10.5px] font-semibold text-low hover:underline">{copied ? "Patch copied" : "Copy suggested patch"}</button>}
      </div>
      {expanded && (
        <div className="mt-3 border-l-2 border-low-line bg-canvas px-3 py-2.5 text-[11px] leading-relaxed text-ink-muted">
          <p>{finding.rationale || "This finding was reported by the selected analyzer."}</p>
          {finding.suggested_patch && <pre className="mt-3 overflow-auto border border-line bg-paper p-2 font-mono text-[10px] text-ink">{finding.suggested_patch}</pre>}
        </div>
      )}
      {finding.status === "open" && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => onStatus("fixed")} className="border border-success-line px-2 py-1 text-[10.5px] font-semibold text-success hover:bg-success-surface">Mark fixed</button>
          <button type="button" onClick={() => onStatus("false_positive")} className="border border-line px-2 py-1 text-[10.5px] font-semibold text-ink-muted hover:bg-canvas">False positive</button>
          <button type="button" onClick={() => onStatus("dismissed")} className="border border-line px-2 py-1 text-[10.5px] font-semibold text-ink-muted hover:bg-canvas">Dismiss</button>
        </div>
      )}
    </article>
  );
}

function ReviewHistory({ reviews, onSelect }: { reviews: Review[]; onSelect: (review: Review) => void }) {
  if (!reviews.length) return null;
  return (
    <section className="mt-4 overflow-hidden rounded-panel border border-line bg-paper" aria-label="Review history">
      <div className="flex items-center justify-between border-b border-line bg-sunken px-4 py-3">
        <h3 className="text-[12px] font-semibold">Review history</h3>
        <span className="font-mono text-[10.5px] text-ink-subtle">{reviews.length}</span>
      </div>
      <div className="divide-y divide-line">
        {reviews.slice(0, 8).map((review) => (
          <button key={review.id} type="button" onClick={() => onSelect(review)} className="grid w-full grid-cols-[1fr_auto] gap-3 px-4 py-3 text-left hover:bg-canvas">
            <span className="min-w-0"><span className="block truncate text-[11.5px] font-semibold">{review.base_branch} → {review.head_branch}</span><span className="block text-[10.5px] text-ink-subtle">{relativeDate(review.created_at, new Date().toISOString())} · {review.model ?? "Local analysis"}</span></span>
            <span className="text-[10.5px] text-ink-muted">{review.findings.length} findings · ${review.stats.cost_usd.toFixed(4)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function CostConfirmation({ preview, model, cap, onCancel, onConfirm }: { preview: DiffPreview; model: string; cap: number | null; onCancel: () => void; onConfirm: () => void }) {
  return (
    <div role="presentation" className="fixed inset-0 z-50 grid place-items-center bg-black/25 p-4">
      <section role="dialog" aria-modal="true" aria-labelledby="cost-confirmation-title" className="w-full max-w-[440px] border border-line bg-paper shadow-2xl">
        <div className="border-b border-line px-5 py-4"><h2 id="cost-confirmation-title" className="text-[15px] font-semibold">Confirm estimated review cost</h2><p className="mt-1 text-[12px] text-ink-muted">This review exceeds your warning threshold.</p></div>
        <div className="space-y-2 px-5 py-4 text-[12px] text-ink-muted"><p><strong className="text-ink">Model:</strong> {model}</p><p><strong className="text-ink">Scope:</strong> {preview.files.length} files, {formatTokens(preview.estimated_tokens)} estimated tokens</p><p><strong className="text-ink">Estimated input:</strong> ${preview.estimated_cost_usd.toFixed(4)}{cap !== null ? ` of $${cap.toFixed(2)} budget` : ""}</p></div>
        <div className="flex justify-end gap-2 border-t border-line px-5 py-4"><button type="button" onClick={onCancel} className="border border-line-strong px-3 py-2 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas">Cancel</button><button type="button" onClick={onConfirm} className="bg-ink px-3 py-2 text-[11.5px] font-semibold text-white hover:bg-zinc-800">Run review</button></div>
      </section>
    </div>
  );
}

function BranchSelect({
  label,
  value,
  branches,
  onChange,
}: {
  label: string;
  value: string;
  branches: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className="mb-1 block text-[9.5px] font-semibold uppercase text-ink-subtle">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 min-w-[150px] rounded-control border border-line-strong bg-paper px-2.5 font-mono text-[11px] outline-none focus:border-ink"
      >
        {branches.map((branch) => (
          <option key={branch}>{branch}</option>
        ))}
      </select>
    </label>
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

function DiffViewer({
  preview,
  loading,
}: {
  preview: DiffPreview | null;
  loading: boolean;
}) {
  if (loading && !preview) {
    return <div className="p-4"><LoadingRows /></div>;
  }

  if (!preview?.patch) {
    return (
      <div className="grid min-h-[360px] place-items-center p-8 text-center">
        <div>
          <Check className="mx-auto mb-3 size-7 text-success" strokeWidth={1.7} />
          <p className="mb-1 text-[12.5px] font-semibold">No changes in this comparison</p>
          <p className="text-[11px] text-ink-muted">
            When base and head match, RevAI previews uncommitted working-tree changes.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-h-[360px] overflow-auto bg-[#fcfcfc]">
      <pre className="min-w-max py-2 text-[11px] leading-[1.65]">
        {preview.patch.split("\n").map((line, index) => {
          const tone = line.startsWith("+")
            ? "bg-success-surface text-[#047857]"
            : line.startsWith("-")
              ? "bg-critical-surface text-[#b91c1c]"
              : line.startsWith("@@")
                ? "bg-low-surface text-low"
                : line.startsWith("diff ") || line.startsWith("index ")
                  ? "font-semibold text-ink"
                  : "text-ink-muted";
          return (
            <code
              key={`${index}-${line}`}
              className={`block min-h-[18px] px-4 ${tone}`}
            >
              {line || " "}
            </code>
          );
        })}
      </pre>
      {preview.truncated && (
        <p className="sticky bottom-0 border-t border-medium-line bg-medium-surface px-4 py-2 text-[10.5px] text-medium">
          Preview capped at 1 MB. The full diff remains unchanged in Git.
        </p>
      )}
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="space-y-2" aria-label="Loading repository data">
      {[70, 92, 58, 80].map((width) => (
        <div
          key={width}
          className="h-5 animate-pulse rounded-chip bg-canvas"
          style={{ width: `${width}%` }}
        />
      ))}
    </div>
  );
}
