import { useBacklinks } from '../hooks';
import { useUiStore } from '../stores';

interface BacklinksPanelProps {
  noteId: number | null;
  className?: string;
}

export function BacklinksPanel({ noteId, className = '' }: BacklinksPanelProps) {
  const { data: backlinks, isLoading, error } = useBacklinks(noteId);
  const selectNote = useUiStore((s) => s.selectNote);

  // No note selected
  if (noteId === null) {
    return (
      <div className={`${className} p-4`}>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Backlinks
        </h3>
        <p className="text-sm text-gray-400">Select a note to see backlinks</p>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className={`${className} p-4`}>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Backlinks
        </h3>
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`${className} p-4`}>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Backlinks
        </h3>
        <p className="text-sm text-red-500">Failed to load backlinks</p>
      </div>
    );
  }

  // Empty state
  if (!backlinks || backlinks.length === 0) {
    return (
      <div className={`${className} p-4`}>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Backlinks
        </h3>
        <p className="text-sm text-gray-400">No notes link to this note</p>
      </div>
    );
  }

  // Backlinks list
  return (
    <div className={`${className} p-4`}>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Backlinks ({backlinks.length})
      </h3>
      <ul className="space-y-1">
        {backlinks.map((backlink) => (
          <li key={backlink.id}>
            <button
              onClick={() => selectNote(backlink.id)}
              className="w-full text-left px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
            >
              <span className="block font-medium truncate">{backlink.title}</span>
              <span className="block text-xs text-gray-400">
                {formatDate(backlink.updated_at)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Helper to format date
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;

  return date.toLocaleDateString();
}
