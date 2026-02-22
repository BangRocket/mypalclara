# Home Menu Redesign — Design

**Goal:** Replace the sidebar navigation with a centered, icon-based tile grid as the landing page. Sharp modern-retro aesthetic using 1-bit pixel art icons and SNES.css accents.

## Architecture

The current sidebar-based navigation (`AppLayout` + `UnifiedSidebar`) is removed entirely. The root route (`/`) becomes a tile grid menu. The current `ChatPage` moves from `/` to `/chat`. Each feature page gets a `FeatureLayout` wrapper (back-to-menu button + title bar) instead of the sidebar.

### Routes

| Path | Component | Notes |
|------|-----------|-------|
| `/` | `HomePage` (new) | Tile grid menu |
| `/chat` | `ChatPage` (moved from `/`) | WebSocket/ChatRuntime scoped here only |
| `/knowledge` | `KnowledgeBasePage` | Unchanged |
| `/graph` | `GraphPage` | Unchanged |
| `/intentions` | `IntentionsPage` | Unchanged |
| `/games/*` | Game pages | Unchanged |
| `/settings` | `SettingsPage` | Unchanged |
| `/admin/*` | Admin pages | Admin-only, conditionally shown |

### What Gets Removed

- `AppLayout.tsx` — replaced by per-feature `FeatureLayout`
- `UnifiedSidebar.tsx` — no sidebar anywhere in the app
- Sidebar-related Zustand state

## Visual Design

**Aesthetic:** Sharp modern-retro — dark background (`#0a0a0f` or similar deep navy-black), crisp pixel icons rendered at 64x64 with `image-rendering: pixelated`, SNES.css for button/container styling accents, Tailwind for layout.

**Grid:** 3-4 columns (responsive), centered on screen. Each tile is a card with:
- 1-bit pixel icon tinted with a per-tile accent color via CSS filter
- Label underneath in a clean sans-serif or pixel-influenced font
- Subtle hover effect (SNES.css button press or glow)

### Tile Assignments

| Tile | Icon Source | Accent Color |
|------|-----------|------|
| Chat | Nikoichu — speech bubble / chat icon | Cyan |
| Knowledge Base | Nikoichu — book / scroll icon | Purple |
| Memory Graph | Nikoichu — network / nodes icon | Green |
| Intentions | Nikoichu — target / crosshair icon | Orange |
| Games | 1-bit chess piece or dice from 10k Game Assets pack | Red |
| Settings | Nikoichu — gear icon | Gray |
| Admin | Nikoichu — shield / key icon | Gold |

## Asset Sources

### Primary: Nikoichu 1-bit Pixel Icons
- 1,476 icons, 16x16, CC0 license, monochrome
- Source: https://nikoichu.itch.io/pixel-icons
- Used for all main menu tile icons
- Rendered at 64x64 with `image-rendering: pixelated`
- Tinted per-tile via CSS

### Supplementary: 10k Game Assets (ci.itch.io)
- `1bit Puzzle and Board/` — chess pieces (13), dice (18) for Games tile
- `Control Prompts/Dark/` — gamepad/keyboard button icons for Games section accents
- `Inventory Icons/` — 320 RPG-style icons, potential for future game-specific tiles

### Supplementary: The Cards (backterria)
- 1-bit card deck — decorative flair on Games tile or background pattern
- High Contrast variant — colorful cards if accent needed
- 64x96px pixel art, multiple deck styles

### Future: Hex Character Pack (snowhex)
- Modular pixel art character portraits
- Could be used for user avatar or Clara mascot on menu page

## Component Structure

```
src/
  pages/
    HomePage.tsx          <- NEW: tile grid landing page
  components/
    MenuTile.tsx          <- NEW: single tile component
    FeatureLayout.tsx     <- NEW: back button + title wrapper (replaces sidebar)
  assets/
    icons/                <- NEW: extracted 1-bit PNGs from Nikoichu
    game-assets/          <- NEW: selected pieces from 10k/cards packs
```

## SNES.css Integration

Import SNES.css via npm (`snes-css`) or CDN. Use selectively:
- `snes-container` for tile card borders
- `snes-button` styling for hover/active states on tiles
- All layout remains Tailwind (SNES.css provides no layout system)

## Data Flow

- `HomePage` reads user role from auth context to conditionally show Admin tile
- No WebSocket connection on home page (saves resources)
- `WebSocketBridge` + `ChatRuntimeProvider` only mount inside `/chat` route
- Navigation is simple React Router `<Link>` — no state to carry

## Key Decisions

1. **No sidebar anywhere** — menu replaces it entirely, each feature uses FeatureLayout with back button
2. **Retro-accented modern** — SNES.css for flavor, not full retro theme
3. **1-bit pixel icons** — sharp, clean, monochrome base tinted with CSS per tile
4. **WebSocket scoped to /chat** — no unnecessary connections on other pages
