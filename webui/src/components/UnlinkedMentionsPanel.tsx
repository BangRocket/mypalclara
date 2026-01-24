import { useUnlinkedMentions } from '../hooks';
import { useUiStore } from '../stores';

interface UnlinkedMentionsPanelProps {
  noteId: number | null;
  noteTitle: string | null;
  className?: string;
}

/**
 * Panel showing notes that mention the current note's title
 * without using wiki link syntax. Helps users discover
 * implicit connections that could become explicit links.
 */
export function UnlinkedMentionsPanel({
  noteId,
  noteTitle,
  className = ''
}: UnlinkedMentionsPanelProps) {
  const { data: mentions, isLoading, error } = useUnlinkedMentions(noteId);
  const selectNote = useUiStore((s) => s.selectNote);

  // No note selected - don't show panel
  if (noteId === null) {
    return null;
  }

  // Loading state
  if (isLoading) {
    return (
      <div className={`${className} p-4`}>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Unlinked Mentions
        </h3>
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  // Error or empty - don't show panel (hide when no mentions)
  if (error || !mentions || mentions.length === 0) {
    return null;
  }

  // Render snippet with title highlighted
  const renderSnippet = (snippet: string) => {
    if (!noteTitle) return snippet;

    // Highlight the mention (case-insensitive)
    const regex = new RegExp(`(${escapeRegex(noteTitle)})`, 'gi');
    return snippet.replace(regex, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>');
  };

  return (
    <div className={`${className} p-4 border-t border-gray-200`}>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Unlinked Mentions ({mentions.length})
      </h3>
      <p className="text-xs text-gray-400 mb-3">
        Notes that mention "{noteTitle}" without linking
      </p>
      <ul className="space-y-2">
        {mentions.map((mention) => (
          <li key={mention.id} className="group">
            <button
              onClick={() => selectNote(mention.id)}
              className="w-full text-left p-2 hover:bg-gray-100 rounded-md transition-colors"
            >
              <span className="block font-medium text-sm text-gray-700 truncate">
                {mention.title}
              </span>
              <span
                className="block text-xs text-gray-500 mt-1 line-clamp-2"
                dangerouslySetInnerHTML={{ __html: renderSnippet(mention.snippet) }}
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Helper to escape regex special characters
function escapeRegex(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
