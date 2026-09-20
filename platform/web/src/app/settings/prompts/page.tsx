/**
 * Settings › Prompts → moved to Settings › Skills & Prompts.
 *
 * The screen outgrew prompts-only configuration: marketplace skills, the
 * default prompts and scenarios now share one screen. This route is kept as a
 * permanent redirect so old bookmarks and links keep working.
 */

import { permanentRedirect } from "next/navigation";

export default function PromptsSettingsPage() {
  permanentRedirect("/settings/skills");
}
