// Bank icon slug map — maps keywords to Material Symbols icon names
// Used in bank cards for visual differentiation per PRD Section D

export const ICON_SLUG_MAP: Record<string, string> = {
  "linux":      "terminal",
  "bash":       "code",
  "python":     "data_object",
  "git":        "merge",
  "docker":     "inventory_2",
  "kubernetes": "hub",
  "terraform":  "account_tree",
  "aws":        "cloud",
  "sql":        "table_chart",
  "dataops":    "sync_alt",
  "regex":      "manage_search",
  "networking": "lan",
  "security":   "shield",
  "default":    "quiz",
};

export function getIconSlug(bank: { icon_slug?: string; chapter?: string; name?: string }): string {
  if (bank.icon_slug && bank.icon_slug !== 'book' && bank.icon_slug !== 'quiz') {
    return bank.icon_slug;
  }
  // Auto-detect from chapter/name
  const text = (bank.chapter || bank.name || '').toLowerCase();
  return Object.entries(ICON_SLUG_MAP).find(([k]) => text.includes(k))?.[1] ?? 'quiz';
}
