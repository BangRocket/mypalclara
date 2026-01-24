---
phase: 03-wiki-links-search
plan: 06
subsystem: ui
tags: [tippy.js, tanstack-query, wiki-links, hover-preview, unlinked-mentions]

# Dependency graph
requires:
  - phase: 03-03
    provides: WikiLink TipTap extension with data-type/data-note-id attributes
  - phase: 03-05
    provides: BacklinksPanel component pattern
  - phase: 03-02
    provides: getUnlinkedMentions Tauri command
provides:
  - WikiLinkPreview component with hover tooltips
  - useUnlinkedMentions hook for fetching unlinked mentions
  - UnlinkedMentionsPanel component for discovering implicit connections
  - Right sidebar layout with BacklinksPanel and UnlinkedMentionsPanel
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Invisible hover management component (returns null, manages DOM events)
    - Editor ref pattern for hover detection
    - Right sidebar for link panels

key-files:
  created:
    - webui/src/editor/components/WikiLinkPreview.tsx
    - webui/src/editor/components/index.ts
    - webui/src/hooks/useUnlinkedMentions.ts
    - webui/src/components/UnlinkedMentionsPanel.tsx
  modified:
    - webui/src/index.css
    - webui/src/components/NoteEditor.tsx
    - webui/src/components/index.ts
    - webui/src/App.tsx
    - webui/src/hooks/index.ts

key-decisions:
  - "WikiLinkPreview is invisible component (returns null) managing hover logic"
  - "Preview caches for 5 minutes, unlinked mentions for 2 minutes"
  - "Unlinked mentions panel only shows when mentions exist (hidden when empty)"
  - "Right sidebar width 256px for link panels"

patterns-established:
  - "Invisible hover manager pattern: component returns null but manages DOM events via ref"
  - "Right sidebar pattern: aside with BacklinksPanel + UnlinkedMentionsPanel"

# Metrics
duration: 12min
completed: 2026-01-24
---

# Phase 3 Plan 6: Link Preview Tooltips and Unlinked Mentions Panel Summary

**Hover previews for wiki links with Tippy.js tooltips, plus unlinked mentions panel showing implicit connections with highlighted snippets**

## Performance

- **Duration:** 12 min
- **Started:** 2026-01-24T02:14:03Z
- **Completed:** 2026-01-24T02:26:00Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- Wiki link hover shows note title and truncated content preview after 300ms delay
- Unlinked mentions panel discovers notes mentioning current note without [[]] syntax
- Right sidebar layout integrates BacklinksPanel and UnlinkedMentionsPanel
- Proper CSS for Tippy.js light-border theme and line-clamp utilities

## Task Commits

Each task was committed atomically:

1. **Task 1: Create WikiLinkPreview component with hover detection** - `0e2560a` (feat)
2. **Task 2: Create useUnlinkedMentions hook and panel** - `03da06a` (feat)
3. **Task 3: Integrate preview and panels into editor layout with CSS** - `94aaf21` (feat)

## Files Created/Modified
- `webui/src/editor/components/WikiLinkPreview.tsx` - Hover preview tooltip component using Tippy.js
- `webui/src/editor/components/index.ts` - Barrel export for editor components
- `webui/src/hooks/useUnlinkedMentions.ts` - TanStack Query hook for unlinked mentions
- `webui/src/components/UnlinkedMentionsPanel.tsx` - Panel showing implicit connections
- `webui/src/index.css` - CSS for wiki-link-preview, Tippy theme, line-clamp utilities
- `webui/src/components/NoteEditor.tsx` - Added editorRef and WikiLinkPreview integration
- `webui/src/components/index.ts` - Export BacklinksPanel and UnlinkedMentionsPanel
- `webui/src/hooks/index.ts` - Export useUnlinkedMentions
- `webui/src/App.tsx` - Right sidebar with link panels, fetch selected note for title

## Decisions Made
- WikiLinkPreview returns null but manages hover logic via DOM events - "invisible" pattern
- 300ms delay before showing preview to avoid flicker on fast mouse movement
- 5 minute cache for note previews, 2 minute cache for unlinked mentions
- UnlinkedMentionsPanel hidden when no mentions (cleaner UI)
- Right sidebar always visible when note selected (no collapse toggle)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 3 (Wiki Links & Search) is now complete
- All wiki link features implemented: extraction, backlinks, unlinked mentions, previews
- Ready for Phase 5 (Chat Integration) or Phase 6 (Clara Note Tools)

---
*Phase: 03-wiki-links-search*
*Completed: 2026-01-24*
