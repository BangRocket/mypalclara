import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import tippy, { Instance as TippyInstance } from 'tippy.js';
import { commands, type Note } from '../../lib/bindings';

interface WikiLinkPreviewProps {
  editorRef: React.RefObject<HTMLDivElement | null>;
  enabled?: boolean;
}

/**
 * Component that adds hover preview tooltips to wiki links in the editor.
 * Must be rendered alongside the TipTap editor.
 *
 * This component is "invisible" - it returns null but manages hover logic
 * for wiki links within the editor container.
 */
export function WikiLinkPreview({ editorRef, enabled = true }: WikiLinkPreviewProps) {
  const [hoveredNoteId, setHoveredNoteId] = useState<number | null>(null);
  const tippyInstance = useRef<TippyInstance | null>(null);
  const targetElement = useRef<HTMLElement | null>(null);

  // Fetch note content for preview
  const { data: note } = useQuery({
    queryKey: ['notePreview', hoveredNoteId],
    queryFn: async (): Promise<Note | null> => {
      if (hoveredNoteId === null) return null;
      const result = await commands.getNote(hoveredNoteId);
      if (result.status === 'error') return null;
      return result.data;
    },
    enabled: hoveredNoteId !== null,
    staleTime: 1000 * 60 * 5, // Cache previews for 5 minutes
  });

  // Set up hover listeners on wiki links
  useEffect(() => {
    if (!enabled || !editorRef.current) return;

    const handleMouseEnter = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const link = target.closest('[data-type="wiki-link"]') as HTMLElement;

      if (link) {
        const noteId = link.getAttribute('data-note-id');
        if (noteId && noteId !== 'null') {
          targetElement.current = link;
          setHoveredNoteId(Number(noteId));
        }
      }
    };

    const handleMouseLeave = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('[data-type="wiki-link"]')) {
        // Small delay to allow moving to tooltip
        setTimeout(() => {
          if (!tippyInstance.current?.state.isShown) {
            setHoveredNoteId(null);
            targetElement.current = null;
          }
        }, 100);
      }
    };

    const editor = editorRef.current;
    editor.addEventListener('mouseover', handleMouseEnter);
    editor.addEventListener('mouseout', handleMouseLeave);

    return () => {
      editor.removeEventListener('mouseover', handleMouseEnter);
      editor.removeEventListener('mouseout', handleMouseLeave);
      tippyInstance.current?.destroy();
    };
  }, [enabled, editorRef]);

  // Show/update tooltip when note data arrives
  useEffect(() => {
    if (!note || !targetElement.current) {
      tippyInstance.current?.destroy();
      tippyInstance.current = null;
      return;
    }

    // Create preview content
    const content = document.createElement('div');
    content.className = 'wiki-link-preview p-3 max-w-sm';
    content.innerHTML = `
      <div class="font-semibold text-gray-900 mb-1">${escapeHtml(note.title)}</div>
      <div class="text-sm text-gray-600 line-clamp-4">${escapeHtml(truncateContent(note.content, 200))}</div>
    `;

    // Create or update tippy instance
    if (tippyInstance.current) {
      tippyInstance.current.setContent(content);
    } else {
      tippyInstance.current = tippy(targetElement.current, {
        content,
        allowHTML: true,
        interactive: true,
        placement: 'bottom-start',
        theme: 'light-border',
        animation: 'fade',
        delay: [300, 100], // Show delay, hide delay
        onHidden: () => {
          setHoveredNoteId(null);
          targetElement.current = null;
        },
      });
      tippyInstance.current.show();
    }
  }, [note]);

  // This component doesn't render anything visible
  return null;
}

// Helpers
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function truncateContent(content: string, maxLength: number): string {
  // Strip markdown-ish syntax for cleaner preview
  const plain = content
    .replace(/#{1,6}\s/g, '') // Remove headers
    .replace(/\*\*([^*]+)\*\*/g, '$1') // Remove bold
    .replace(/\*([^*]+)\*/g, '$1') // Remove italic
    .replace(/\[\[([^\]]+)\]\]/g, '$1') // Remove wiki link brackets
    .trim();

  if (plain.length <= maxLength) return plain;
  return plain.slice(0, maxLength) + '...';
}
