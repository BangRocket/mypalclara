/**
 * Groups threads by time period.
 * Since thread objects don't expose timestamps to the UI,
 * we group by position (most recent first from the API).
 */

export interface ThreadItem {
  id: string;
  title?: string;
  status: "regular" | "archived";
}

export interface ThreadGroup {
  label: string;
  threads: ThreadItem[];
}

export function groupThreadsByTime(threads: ThreadItem[]): ThreadGroup[] {
  const groups: ThreadGroup[] = [];
  if (threads.length === 0) return groups;

  const recent = threads.slice(0, 5);
  const earlier = threads.slice(5, 15);
  const older = threads.slice(15);

  if (recent.length > 0) groups.push({ label: "Recent", threads: recent });
  if (earlier.length > 0) groups.push({ label: "Earlier", threads: earlier });
  if (older.length > 0) groups.push({ label: "Older", threads: older });

  return groups;
}
