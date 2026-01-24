---
phase: 02-core-notes
plan: 01
subsystem: ui
tags: [tailwind, zustand, tanstack-query, tiptap, postcss, vite]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: React 19 + Vite build toolchain
provides:
  - Tailwind CSS v4 configured with @tailwindcss/postcss and typography plugin
  - Zustand store for UI state (note/folder selection, sidebar collapsed)
  - TanStack Query provider for data fetching with sensible defaults
  - TipTap editor libraries installed and ready for integration
affects: [02-02-layout, 02-03-note-list, 02-04-editor, all UI development]

# Tech tracking
tech-stack:
  added:
    - "@tiptap/react@3.17.0 - Rich text editor framework"
    - "@tiptap/pm@3.17.0 - ProseMirror core"
    - "@tiptap/starter-kit@3.17.0 - Basic editor extensions"
    - "@tiptap/extension-placeholder@3.17.0 - Placeholder support"
    - "zustand@5.0.10 - State management"
    - "@tanstack/react-query@5.90.20 - Data fetching and caching"
    - "tailwindcss@4.1.18 - Utility-first CSS"
    - "@tailwindcss/postcss@latest - v4 PostCSS plugin"
    - "@tailwindcss/typography@0.5.19 - Prose styling"
    - "autoprefixer@10.4.23 - CSS vendor prefixes"
  patterns:
    - "Zustand stores: create<T>() with typed state and actions"
    - "Tailwind v4: @import \"tailwindcss\" instead of @tailwind directives"
    - "TanStack Query: QueryClientProvider at app root with staleTime 1min"

key-files:
  created:
    - webui/tailwind.config.js
    - webui/postcss.config.js
    - webui/src/index.css
    - webui/src/stores/uiStore.ts
    - webui/src/stores/index.ts
  modified:
    - webui/package.json
    - webui/src/main.tsx

key-decisions:
  - "Tailwind v4 requires @tailwindcss/postcss instead of direct tailwindcss plugin"
  - "@import \"tailwindcss\" replaces @tailwind base/components/utilities directives"
  - "Avoid @apply in Tailwind v4 - use native CSS or inline utility classes"
  - "QueryClient staleTime 1 minute, refetchOnWindowFocus disabled"
  - "uiStore tracks selectedNoteId, selectedFolderId, sidebarCollapsed"

patterns-established:
  - "Store structure: state fields + action functions in create<T>()"
  - "Barrel exports: stores/index.ts re-exports all stores"
  - "Tailwind config: content paths cover all .tsx/.jsx files"

# Metrics
duration: 3min
completed: 2026-01-23
---

# Phase 2 Plan 1: Frontend Stack Setup Summary

**Tailwind v4 + Zustand + TanStack Query + TipTap dependencies configured for Phase 2 UI development**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-23T18:26:41Z
- **Completed:** 2026-01-23T18:30:01Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- All 8 frontend dependencies installed (TipTap editor, Zustand state, TanStack Query, Tailwind CSS)
- Tailwind v4 configured with @tailwindcss/postcss and typography plugin
- Zustand uiStore created with note/folder selection and sidebar state
- TanStack Query provider wrapping app with 1-minute stale time

## Task Commits

Each task was committed atomically:

1. **Task 01: Install frontend dependencies** - `d545ad6` (docs)
   - Task already completed in prior session, verified all packages present

2. **Task 02: Configure Tailwind CSS** - `aa02970` (feat)
   - Adapted to Tailwind v4: @tailwindcss/postcss, @import directive
   - Build succeeds without PostCSS errors

3. **Task 03: Set up Zustand store and TanStack Query** - `01dfec4` (feat)
   - Created uiStore with selection state and actions
   - Wrapped app in QueryClientProvider

## Files Created/Modified

- `webui/package.json` - Added 8 dependencies (TipTap, Zustand, TanStack Query, Tailwind)
- `webui/tailwind.config.js` - Tailwind v4 config with content paths and typography plugin
- `webui/postcss.config.js` - @tailwindcss/postcss + autoprefixer
- `webui/src/index.css` - @import "tailwindcss" with custom root styles
- `webui/src/stores/uiStore.ts` - UI state management (note/folder selection, sidebar)
- `webui/src/stores/index.ts` - Barrel exports for stores
- `webui/src/main.tsx` - Added QueryClientProvider and imported index.css

## Decisions Made

**Tailwind v4 migration:** Discovered Tailwind v4 requires @tailwindcss/postcss plugin instead of direct tailwindcss in postcss.config.js. Also changed CSS from @tailwind directives to @import "tailwindcss". This is a breaking change in v4 but necessary for the build to succeed.

**@apply removal:** Tailwind v4 doesn't support @apply with utility classes in the same way as v3. Changed body styles from `@apply bg-gray-50 text-gray-900` to native CSS `background-color: #f9fafb; color: #111827;`.

**Store structure:** uiStore tracks selectedNoteId, selectedFolderId, and sidebarCollapsed as the minimal UI state needed for Phase 2 layout/navigation. Actions use simple set() calls for immediate updates.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tailwind v4 PostCSS plugin requirement**
- **Found during:** Task 2 (Configure Tailwind CSS)
- **Issue:** Build failed with error "PostCSS plugin has moved to separate package" when using tailwindcss directly
- **Fix:** Installed @tailwindcss/postcss and updated postcss.config.js to use '@tailwindcss/postcss' instead of 'tailwindcss'
- **Files modified:** webui/package.json, webui/postcss.config.js
- **Verification:** `npm run build` succeeded without PostCSS errors
- **Committed in:** aa02970 (Task 2 commit)

**2. [Rule 3 - Blocking] Tailwind v4 directive syntax change**
- **Found during:** Task 2 (Configure Tailwind CSS)
- **Issue:** Build failed with "Cannot apply unknown utility class" when using @tailwind directives and @apply
- **Fix:** Changed index.css from @tailwind base/components/utilities to @import "tailwindcss", replaced @apply with native CSS
- **Files modified:** webui/src/index.css
- **Verification:** `npm run build` succeeded, CSS processed correctly
- **Committed in:** aa02970 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes required for Tailwind v4 compatibility. Plan assumed v3 syntax but dependencies installed v4. No scope creep - just version adaptation.

## Issues Encountered

**Task 01 already completed:** Package installations from a prior session were already present. Verified via `npm ls` and continued to Task 02.

**Tailwind v4 breaking changes:** The plan was written for Tailwind v3 syntax but v4 was installed. Required adapting PostCSS config and CSS directives. This is a known breaking change in Tailwind v4 (PostCSS plugin moved to separate package, new @import syntax).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 2 Plan 02 (Layout Component):**
- Tailwind classes will work in React components
- uiStore ready for sidebar and selection state
- TanStack Query ready for data fetching hooks
- TipTap libraries ready for editor integration

**No blockers or concerns.** Build succeeds, all dependencies functional.

---
*Phase: 02-core-notes*
*Completed: 2026-01-23*
