"use client";

import { Check, ChevronsUpDown, GitBranch, Search } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";

export function BranchSelect({
  label,
  value,
  branches,
  onChange,
  className = "w-[170px]",
}: {
  label: string;
  value: string;
  branches: string[];
  onChange: (value: string) => void;
  className?: string;
}) {
  const { t } = useUiText();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();
  const labelId = useId();
  const valueId = useId();

  const filteredBranches = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return branches;
    return branches.filter((branch) => branch.toLocaleLowerCase().includes(normalized));
  }, [branches, query]);

  const openSelector = () => {
    const selectedIndex = branches.indexOf(value);
    setQuery("");
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setOpen(true);
  };

  const closeSelector = (restoreFocus: boolean) => {
    setOpen(false);
    setQuery("");
    if (restoreFocus) requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const selectBranch = (branch: string) => {
    if (!branches.includes(branch)) return;
    if (branch === value) {
      closeSelector(true);
      return;
    }
    onChange(branch);
    closeSelector(true);
  };

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();

    const dismissOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) closeSelector(false);
    };
    document.addEventListener("pointerdown", dismissOutside);
    return () => document.removeEventListener("pointerdown", dismissOutside);
  }, [open]);

  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeSelector(true);
      return;
    }
    if (event.key === "Tab") {
      closeSelector(false);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) =>
        filteredBranches.length ? (current + 1) % filteredBranches.length : 0,
      );
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) =>
        filteredBranches.length
          ? (current - 1 + filteredBranches.length) % filteredBranches.length
          : 0,
      );
      return;
    }
    if (event.key === "Home" && filteredBranches.length) {
      event.preventDefault();
      setActiveIndex(0);
      return;
    }
    if (event.key === "End" && filteredBranches.length) {
      event.preventDefault();
      setActiveIndex(filteredBranches.length - 1);
      return;
    }
    if (event.key === "Enter" && filteredBranches[activeIndex]) {
      event.preventDefault();
      selectBranch(filteredBranches[activeIndex]);
    }
  };

  return (
    <div
      ref={rootRef}
      className={`relative min-w-0 ${className}`}
      onBlurCapture={(event) => {
        if (!rootRef.current?.contains(event.relatedTarget as Node | null)) {
          closeSelector(false);
        }
      }}
    >
      <span
        id={labelId}
        className="mb-1 block text-[9.5px] font-semibold uppercase tracking-[0.08em] text-ink-subtle"
      >
        {t(label)}
      </span>
      <button
        ref={triggerRef}
        type="button"
        aria-labelledby={`${labelId} ${valueId}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        onClick={() => (open ? closeSelector(false) : openSelector())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (!open) openSelector();
          }
        }}
        className="flex h-9 w-full items-center gap-2 rounded-control border border-line-strong bg-paper px-2.5 text-left font-mono text-[11px] text-ink outline-none hover:bg-canvas focus:border-ink"
      >
        <GitBranch className="size-3.5 shrink-0 text-ink-subtle" aria-hidden="true" />
        <span id={valueId} className="min-w-0 flex-1 truncate">{value}</span>
        <ChevronsUpDown className="size-3.5 shrink-0 text-ink-subtle" aria-hidden="true" />
      </button>
      {open ? (
        <div className="absolute left-0 top-full z-40 mt-1.5 w-full min-w-[240px] rounded-control border border-line-strong bg-paper p-1.5 shadow-xl">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-subtle"
              aria-hidden="true"
            />
            <input
              ref={inputRef}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded="true"
              aria-controls={listboxId}
              aria-activedescendant={
                filteredBranches[activeIndex] ? `${listboxId}-option-${activeIndex}` : undefined
              }
              aria-label={`${t("Search branches")} — ${t(label)}`}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={handleSearchKeyDown}
              placeholder={t("Search branches")}
              className="h-8 w-full rounded-chip border border-line bg-sunken pl-8 pr-2 font-mono text-[11px] text-ink outline-none placeholder:text-ink-subtle focus:border-ink"
            />
          </div>
          <div id={listboxId} role="listbox" aria-labelledby={labelId} className="mt-1 max-h-56 overflow-auto">
            {filteredBranches.length ? (
              filteredBranches.map((branch, index) => (
                <button
                  key={branch}
                  id={`${listboxId}-option-${index}`}
                  type="button"
                  role="option"
                  tabIndex={-1}
                  aria-selected={branch === value}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => selectBranch(branch)}
                  className={`flex w-full min-w-0 items-center gap-2 rounded-chip px-2 py-1.5 text-left font-mono text-[11px] ${
                    index === activeIndex ? "bg-canvas text-ink" : "text-ink-muted hover:bg-canvas"
                  }`}
                >
                  <Check
                    className={`size-3.5 shrink-0 ${branch === value ? "opacity-100" : "opacity-0"}`}
                    aria-hidden="true"
                  />
                  <span className="truncate">{branch}</span>
                </button>
              ))
            ) : (
              <p role="status" className="px-2 py-3 text-center text-[11px] text-ink-subtle">
                {t("No branches match your search.")}
              </p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
