import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SETTINGS_MENU, TopBar } from "@/components/top-bar";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
// The banner has its own suite; here it must not pull in the real store.
vi.mock("@/components/connection-banner", () => ({ ConnectionBanner: () => null }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
  useLinkStatus: () => ({ pending: false }),
}));

function hrefs(): string[] {
  return screen.getAllByRole("link").map((link) => link.getAttribute("href") ?? "");
}

afterEach(cleanup);

describe("primary navigation", () => {
  it("keeps settings sub-pages out of the top level", () => {
    render(<TopBar />);

    // The wide nav renders the top-level entries; the collapsed menu renders both
    // lists, so counting occurrences separates "top level" from "in the menu".
    const settingsHrefs = SETTINGS_MENU.map((item) => item.href);
    for (const href of settingsHrefs) {
      const occurrences = hrefs().filter((candidate) => candidate === href).length;
      expect(occurrences, `${href} must appear once, in the settings menu only`).toBe(1);
    }
  });

  it("offers documentation as an external top-level destination", () => {
    render(<TopBar />);

    const docsLinks = screen.getAllByRole("link").filter((link) =>
      (link.getAttribute("href") ?? "").endsWith(":3001"),
    );
    expect(docsLinks).toHaveLength(2);
    for (const link of docsLinks) {
      expect(link.getAttribute("target")).toBe("_blank");
      expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    }
  });

  it("lists the connection screen in the settings menu", () => {
    expect(SETTINGS_MENU.map((item) => item.href)).toContain("/settings/connection");
  });

  it("defines the settings menu once, for both surfaces", () => {
    render(<TopBar breadcrumb={[{ label: "common.settings", menu: SETTINGS_MENU }, "common.engine"]} />);

    // The breadcrumb dropdown and the nav dropdown are fed by the same array, so a
    // page added to it cannot exist in one and be missing from the other.
    expect(new Set(SETTINGS_MENU.map((item) => item.href)).size).toBe(SETTINGS_MENU.length);
  });

  it("gives the collapsed menu the same destinations as the wide layout", () => {
    const { container } = render(<TopBar />);
    const collapsed = container.querySelector("details nav");
    const collapsedHrefs = [...(collapsed?.querySelectorAll("a") ?? [])].map((link) =>
      link.getAttribute("href"),
    );

    const expected = [
      "/",
      "/insights",
      "http://127.0.0.1:3001",
      ...SETTINGS_MENU.map((item) => item.href),
    ];
    expect(collapsedHrefs).toEqual(expected);
  });
});

describe("projects screen", () => {
  it("no longer renders a connection indicator", () => {
    // Structural rather than rendered: the screen is an async server component. The
    // chip's component is gone and the screen must not reference one.
    const web = process.cwd();
    expect(existsSync(join(web, "src", "components", "api-status-badge.tsx"))).toBe(false);

    const home = readFileSync(join(web, "src", "app", "page.tsx"), "utf8");
    expect(home).not.toContain("ApiStatusBadge");
    expect(home).not.toContain("apiConnected");
  });
});
