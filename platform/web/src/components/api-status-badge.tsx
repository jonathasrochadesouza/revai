"use client";

import { Badge } from "@/components/ui/badge";
import { useUiText } from "@/components/ui-preference-bootstrap";

/** API status chip for the projects header. */
export function ApiStatusBadge({ connected }: { connected: boolean }) {
  const { t } = useUiText();
  return (
    <span className="hidden sm:inline-flex">
      <Badge tone={connected ? "success" : "critical"} dot>
        {connected ? t("common.apiConnected") : t("common.apiUnreachable")}
      </Badge>
    </span>
  );
}
