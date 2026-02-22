# Home Menu Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace sidebar navigation with a centered, icon-based tile grid landing page using 1-bit pixel art and SNES.css accents.

**Architecture:** Remove `AppLayout` (sidebar wrapper) from the route tree. The root route `/` becomes a new `HomePage` tile grid. `ChatPage` moves to `/chat`. Each feature page wraps in a new `FeatureLayout` component (back button + title) instead of sidebar. `WebSocketBridge`/`ChatRuntimeProvider` scope to `/chat` only.

**Tech Stack:** React 19, React Router 7, Tailwind CSS 4, SNES.css, Zustand, TypeScript, 1-bit pixel PNGs (Nikoichu CC0)

---

### Task 1: Install SNES.css and Prepare Icon Assets

**Files:**
- Modify: `web-ui/frontend/package.json`
- Modify: `web-ui/frontend/src/index.css:1-3`
- Create: `web-ui/frontend/src/assets/icons/chat.png`
- Create: `web-ui/frontend/src/assets/icons/knowledge.png`
- Create: `web-ui/frontend/src/assets/icons/graph.png`
- Create: `web-ui/frontend/src/assets/icons/intentions.png`
- Create: `web-ui/frontend/src/assets/icons/games.png`
- Create: `web-ui/frontend/src/assets/icons/settings.png`
- Create: `web-ui/frontend/src/assets/icons/admin.png`

**Step 1: Install snes.css**

```bash
cd web-ui/frontend && pnpm add snes.css
```

**Step 2: Import snes.css in global styles**

In `web-ui/frontend/src/index.css`, add after line 2 (`@import "tw-animate-css";`):

```css
@import "snes.css/dist/snes.min.css";
```

**Step 3: Extract icon PNGs from Nikoichu set**

The Nikoichu 1-bit pixel icons pack is at `/tmp/clara-assets/` (or wherever Joshua has them). We need 7 icons, each a 16x16 monochrome PNG. Copy/extract relevant icons into `web-ui/frontend/src/assets/icons/`:

- `chat.png` — speech bubble icon
- `knowledge.png` — book or scroll icon
- `graph.png` — network/nodes icon
- `intentions.png` — target/crosshair icon
- `games.png` — dice or chess piece (can use from 10k Game Assets `1bit Puzzle and Board/dice/`)
- `settings.png` — gear icon
- `admin.png` — shield or key icon

If the exact icons aren't available yet, create temporary 16x16 placeholder PNGs (single-color squares) so development can proceed. Joshua will provide final icons.

**Step 4: Copy game-specific assets**

From the 10k Game Assets pack, copy relevant 1-bit pieces for decorative use:

```bash
mkdir -p web-ui/frontend/src/assets/game-assets
# Copy 1-bit dice and chess pieces for Games tile decoration
cp "/tmp/clara-assets/10k/Pixel Art (4574)/1bit Puzzle and Board (269)/dice/"*.png \
   web-ui/frontend/src/assets/game-assets/ 2>/dev/null || true
```

**Step 5: Commit**

```bash
git add web-ui/frontend/package.json web-ui/frontend/pnpm-lock.yaml \
        web-ui/frontend/src/index.css web-ui/frontend/src/assets/
git commit -m "feat: install snes.css and add pixel icon assets"
```

---

### Task 2: Create FeatureLayout Component

This component replaces the sidebar for all feature pages — provides a back-to-menu button and page title.

**Files:**
- Create: `web-ui/frontend/src/components/layout/FeatureLayout.tsx`

**Step 1: Create the component**

Create `web-ui/frontend/src/components/layout/FeatureLayout.tsx`:

```tsx
import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FeatureLayoutProps {
  title: string;
  children: ReactNode;
}

export function FeatureLayout({ title, children }: FeatureLayoutProps) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-border px-4 py-3">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/">
            <ArrowLeft size={20} />
          </Link>
        </Button>
        <h1 className="text-sm font-semibold">{title}</h1>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
```

**Step 2: Verify it compiles**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -5
```

Expected: Build succeeds (component is unused so far, but should compile without errors).

**Step 3: Commit**

```bash
git add web-ui/frontend/src/components/layout/FeatureLayout.tsx
git commit -m "feat: add FeatureLayout component (back button + title bar)"
```

---

### Task 3: Create MenuTile Component

The reusable tile component for the home grid.

**Files:**
- Create: `web-ui/frontend/src/components/MenuTile.tsx`

**Step 1: Create the component**

Create `web-ui/frontend/src/components/MenuTile.tsx`:

```tsx
import { Link } from "react-router-dom";

interface MenuTileProps {
  to: string;
  label: string;
  icon: string;
  accentColor: string;
  badge?: number;
}

export function MenuTile({ to, label, icon, accentColor, badge }: MenuTileProps) {
  return (
    <Link
      to={to}
      className="snes-container group relative flex flex-col items-center justify-center gap-3 p-6 transition-transform hover:scale-105 active:scale-95"
      style={{ "--tile-accent": accentColor } as React.CSSProperties}
    >
      <img
        src={icon}
        alt={label}
        className="h-16 w-16"
        draggable={false}
        style={{
          imageRendering: "pixelated",
          filter: `brightness(0) saturate(100%) drop-shadow(0 0 1px ${accentColor})`,
        }}
      />
      <span className="text-sm font-medium text-foreground">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="absolute right-2 top-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white">
          {badge}
        </span>
      )}
    </Link>
  );
}
```

**Note on icon tinting:** The `filter: brightness(0)` makes the white 1-bit icon black, then `drop-shadow` adds the colored glow. If the icons are black-on-transparent, use `filter: invert(1)` first. This will need testing with the actual icons — adjust the filter in Step 3.

**Step 2: Verify it compiles**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -5
```

Expected: Build succeeds.

**Step 3: Test with actual icons and adjust filter**

Once icons are in place, visually verify the tinting looks right. If icons are black-on-transparent (typical for 1-bit), the filter chain should be:

```css
filter: invert(1) drop-shadow(0 0 2px ${accentColor});
```

If icons are white-on-transparent:

```css
filter: drop-shadow(0 0 2px ${accentColor});
```

Adjust based on visual result.

**Step 4: Commit**

```bash
git add web-ui/frontend/src/components/MenuTile.tsx
git commit -m "feat: add MenuTile component for home grid"
```

---

### Task 4: Create HomePage Component

The new tile grid landing page.

**Files:**
- Create: `web-ui/frontend/src/pages/HomePage.tsx`

**Step 1: Create the page**

Create `web-ui/frontend/src/pages/HomePage.tsx`:

```tsx
import { useAuth } from "@/auth/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import { MenuTile } from "@/components/MenuTile";
import { admin } from "@/api/client";

// Icon imports — these resolve to URLs via Vite's asset handling
import chatIcon from "@/assets/icons/chat.png";
import knowledgeIcon from "@/assets/icons/knowledge.png";
import graphIcon from "@/assets/icons/graph.png";
import intentionsIcon from "@/assets/icons/intentions.png";
import gamesIcon from "@/assets/icons/games.png";
import settingsIcon from "@/assets/icons/settings.png";
import adminIcon from "@/assets/icons/admin.png";

export function HomePage() {
  const { user } = useAuth();
  const isAdmin = user?.is_admin === true;

  const { data: pendingData } = useQuery({
    queryKey: ["admin", "pendingCount"],
    queryFn: () => admin.pendingCount(),
    enabled: isAdmin,
  });

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      {/* Title */}
      <h1 className="mb-2 text-3xl font-bold text-foreground">Clara</h1>
      <p className="mb-10 text-sm text-muted-foreground">What would you like to do?</p>

      {/* Tile grid */}
      <div className="grid w-full max-w-2xl grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <MenuTile to="/chat" label="Chat" icon={chatIcon} accentColor="#22d3ee" />
        <MenuTile to="/knowledge" label="Knowledge" icon={knowledgeIcon} accentColor="#a855f7" />
        <MenuTile to="/graph" label="Graph" icon={graphIcon} accentColor="#22c55e" />
        <MenuTile to="/intentions" label="Intentions" icon={intentionsIcon} accentColor="#f97316" />
        <MenuTile to="/games" label="Games" icon={gamesIcon} accentColor="#ef4444" />
        <MenuTile to="/settings" label="Settings" icon={settingsIcon} accentColor="#9ca3af" />
        {isAdmin && (
          <MenuTile
            to="/admin/users"
            label="Admin"
            icon={adminIcon}
            accentColor="#eab308"
            badge={pendingData?.count}
          />
        )}
      </div>
    </div>
  );
}
```

**Step 2: Verify it compiles**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -5
```

Expected: Build succeeds. If icons don't exist yet, build will fail on the imports — create placeholder PNGs first (Task 1, Step 3).

**Step 3: Commit**

```bash
git add web-ui/frontend/src/pages/HomePage.tsx
git commit -m "feat: add HomePage tile grid component"
```

---

### Task 5: Rewire Routes — Remove Sidebar, Scope WebSocket to /chat

This is the critical task. We restructure `App.tsx` to:
1. Remove `AppLayout` (sidebar) from the route tree
2. Move `ChatPage` from `/` to `/chat`
3. Add `HomePage` at `/`
4. Scope `WebSocketBridge`/`ChatRuntimeProvider` to `/chat` only
5. Wrap each feature page in `FeatureLayout`

**Files:**
- Modify: `web-ui/frontend/src/App.tsx`

**Step 1: Rewrite App.tsx**

Replace the entire contents of `web-ui/frontend/src/App.tsx` with:

```tsx
import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthProvider";
import { ChatRuntimeProvider } from "@/components/chat/ChatRuntimeProvider";
import { FeatureLayout } from "@/components/layout/FeatureLayout";
import { useWebSocket } from "@/hooks/useWebSocket";
import { LoginPage } from "@/pages/Login";
import { HomePage } from "@/pages/HomePage";
import { KnowledgeBasePage } from "@/pages/KnowledgeBase";
import { ChatPage } from "@/pages/Chat";
import { GraphExplorerPage } from "@/pages/GraphExplorer";
import { SettingsPage } from "@/pages/Settings";
import { IntentionsPage } from "@/pages/Intentions";
import { OAuthCallback } from "@/auth/OAuthCallback";
import { PendingApproval } from "@/pages/PendingApproval";
import { SuspendedPage } from "@/pages/Suspended";
import { AdminUsersPage } from "@/pages/AdminUsers";
import Lobby from "@/pages/Lobby";
import Blackjack from "@/pages/Blackjack";
import Checkers from "@/pages/Checkers";
import GameHistory from "@/pages/GameHistory";
import Replay from "@/pages/Replay";
import { api } from "@/api/client";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.status === "pending") return <Navigate to="/pending" replace />;
  if (user.status === "suspended") return <Navigate to="/suspended" replace />;
  return <>{children}</>;
}

/** Connects WebSocket when authenticated. Wraps children in ChatRuntimeProvider. */
function WebSocketBridge({ children }: { children: React.ReactNode }) {
  useWebSocket();
  return <ChatRuntimeProvider>{children}</ChatRuntimeProvider>;
}

/** Routes to the correct game component based on game_type. */
function GameRouter() {
  const { id } = useParams();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data, isLoading } = useQuery<any>({
    queryKey: ["game", id],
    queryFn: () => api.games.show(id!),
  });
  if (isLoading) return <div style={{ minHeight: "100vh", background: "#0a0a0a", display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontFamily: "monospace" }}>Loading...</div>;
  if (!data?.game) return <div style={{ minHeight: "100vh", background: "#0a0a0a", display: "flex", alignItems: "center", justifyContent: "center", color: "#ef4444", fontFamily: "monospace" }}>Game not found</div>;
  if (data.game.game_type === "checkers") return <Checkers game={data.game} />;
  return <Blackjack game={data.game} />;
}

export function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback/:provider" element={<OAuthCallback />} />
      <Route path="/pending" element={<PendingApproval />} />
      <Route path="/suspended" element={<SuspendedPage />} />

      {/* Protected — Home page (no WebSocket, no sidebar) */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />

      {/* Protected — Chat (WebSocket scoped here only) */}
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <WebSocketBridge>
              <FeatureLayout title="Chat">
                <ChatPage />
              </FeatureLayout>
            </WebSocketBridge>
          </ProtectedRoute>
        }
      />

      {/* Protected — Feature pages (no WebSocket, FeatureLayout wrapper) */}
      <Route
        path="/knowledge"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Knowledge Base">
              <KnowledgeBasePage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/graph"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Memory Graph">
              <GraphExplorerPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/intentions"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Intentions">
              <IntentionsPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Settings">
              <SettingsPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Admin">
              <AdminUsersPage />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />

      {/* Protected — Games (own layouts, no sidebar) */}
      <Route
        path="/games"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Games">
              <Lobby />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/games/history"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Game History">
              <GameHistory />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/games/history/:id"
        element={
          <ProtectedRoute>
            <FeatureLayout title="Replay">
              <Replay />
            </FeatureLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/games/:id"
        element={
          <ProtectedRoute>
            <GameRouter />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
```

**Key changes from current `App.tsx`:**
1. `AppLayout` import removed entirely
2. `HomePage` imported and rendered at `/`
3. `ChatPage` moved from `/` to `/chat`
4. `WebSocketBridge` wraps only the `/chat` route (not all protected routes)
5. Each feature route gets its own `<ProtectedRoute><FeatureLayout>...</FeatureLayout></ProtectedRoute>` wrapper
6. Game routes (`/games/:id`) remain unwrapped by FeatureLayout since Blackjack/Checkers have their own full-screen layouts

**Step 2: Verify build**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -10
```

Expected: Build succeeds with no errors.

**Step 3: Commit**

```bash
git add web-ui/frontend/src/App.tsx
git commit -m "feat: rewire routes — tile grid home, scoped WebSocket, FeatureLayout"
```

---

### Task 6: Update Chat Page for New Context

The `ChatPage` previously assumed it was at `/` inside `AppLayout`. Now it's at `/chat` inside `FeatureLayout`. The thread list was in the sidebar — we need to decide where it goes.

**Files:**
- Modify: `web-ui/frontend/src/pages/Chat.tsx`

**Step 1: Review current ChatPage**

Read `web-ui/frontend/src/pages/Chat.tsx`. It currently renders `<Thread />` from assistant-ui. The thread list was in `UnifiedSidebar` (only shown when `isOnChat` was true). Now that there's no sidebar, the thread list needs to be accessible from the Chat page itself.

**Step 2: Add thread list to Chat page**

Modify `web-ui/frontend/src/pages/Chat.tsx` to include a collapsible thread list panel on the left:

```tsx
import { useState } from "react";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { ArtifactPanel } from "@/components/chat/ArtifactPanel";
import { useChatStore } from "@/stores/chatStore";
import { useArtifactStore } from "@/stores/artifactStore";
import { Button } from "@/components/ui/button";
import { PanelLeftOpen, PanelLeftClose } from "lucide-react";

export function ChatPage() {
  const connectionError = useChatStore((s) => s.connectionError);
  const connected = useChatStore((s) => s.connected);
  const panelOpen = useArtifactStore((s) => s.panelOpen);
  const hasArtifacts = useArtifactStore((s) => s.artifacts.length > 0);
  const [threadsOpen, setThreadsOpen] = useState(false);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {connectionError && (
        <div className="shrink-0 border-b border-destructive bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {connectionError}
        </div>
      )}
      {!connected && !connectionError && (
        <div className="shrink-0 border-b border-border bg-muted px-4 py-2 text-sm text-muted-foreground">
          Connecting...
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        {/* Thread list panel */}
        {threadsOpen && (
          <div className="w-64 shrink-0 overflow-y-auto border-r border-border bg-card">
            <ThreadList />
          </div>
        )}

        {/* Chat area */}
        <div className="flex flex-1 flex-col">
          {/* Thread toggle */}
          <div className="flex shrink-0 items-center border-b border-border px-2 py-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setThreadsOpen(!threadsOpen)}
              title={threadsOpen ? "Hide threads" : "Show threads"}
            >
              {threadsOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
            </Button>
          </div>
          <div className="flex-1 overflow-hidden">
            <Thread />
          </div>
        </div>

        {panelOpen && hasArtifacts && <ArtifactPanel />}
      </div>
    </div>
  );
}
```

**Step 3: Verify build**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -5
```

Expected: Build succeeds.

**Step 4: Commit**

```bash
git add web-ui/frontend/src/pages/Chat.tsx
git commit -m "feat: add inline thread list panel to Chat page"
```

---

### Task 7: Add Dark Theme Overrides for Home Page

The design calls for a deep dark background (`#0a0a0f`). We should ensure the home page looks sharp in both light and dark mode, with the dark mode being the "hero" experience.

**Files:**
- Modify: `web-ui/frontend/src/index.css`

**Step 1: Add home page specific styles**

Add to the end of `web-ui/frontend/src/index.css` (before the closing, after the Tiptap styles):

```css
/* Home menu tile styles */
.snes-container {
  cursor: pointer;
  text-decoration: none;
  display: flex;
}

/* Pixel art rendering */
.pixelated {
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}
```

**Step 2: Verify build**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -5
```

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add web-ui/frontend/src/index.css
git commit -m "feat: add home menu CSS utilities"
```

---

### Task 8: Clean Up — Remove AppLayout and UnifiedSidebar

Now that no route references `AppLayout` or `UnifiedSidebar`, remove them.

**Files:**
- Delete: `web-ui/frontend/src/components/layout/AppLayout.tsx`
- Delete: `web-ui/frontend/src/components/layout/UnifiedSidebar.tsx`

**Step 1: Verify no remaining imports**

Search for any remaining references to `AppLayout` or `UnifiedSidebar`:

```bash
cd web-ui/frontend && grep -r "AppLayout\|UnifiedSidebar" src/ --include="*.tsx" --include="*.ts"
```

Expected: No results (the only reference was in `App.tsx`, which was rewritten in Task 5). If there ARE results, update those files first.

**Step 2: Delete the files**

```bash
rm web-ui/frontend/src/components/layout/AppLayout.tsx
rm web-ui/frontend/src/components/layout/UnifiedSidebar.tsx
```

**Step 3: Verify build**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -10
```

Expected: Build succeeds with no errors about missing modules.

**Step 4: Commit**

```bash
git add -u web-ui/frontend/src/components/layout/
git commit -m "chore: remove AppLayout and UnifiedSidebar (replaced by FeatureLayout + tile grid)"
```

---

### Task 9: Add Theme Toggle and User Menu to FeatureLayout

The sidebar previously had the theme toggle and user avatar/logout. Now that the sidebar is gone, we need these somewhere. Add them to `FeatureLayout`'s header bar.

**Files:**
- Modify: `web-ui/frontend/src/components/layout/FeatureLayout.tsx`

**Step 1: Add theme toggle and user menu**

Update `web-ui/frontend/src/components/layout/FeatureLayout.tsx`:

```tsx
import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Sun, Moon, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/auth/AuthProvider";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

interface FeatureLayoutProps {
  title: string;
  children: ReactNode;
}

export function FeatureLayout({ title, children }: FeatureLayoutProps) {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-border px-4 py-2">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/">
            <ArrowLeft size={18} />
          </Link>
        </Button>
        <h1 className="text-sm font-semibold">{title}</h1>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Theme toggle */}
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </Button>

        {/* User */}
        {user && (
          <div className="flex items-center gap-2">
            <Avatar className="h-6 w-6">
              <AvatarImage src={user.avatar_url || undefined} />
              <AvatarFallback className="text-[10px]">
                {user.display_name?.[0]?.toUpperCase() || "?"}
              </AvatarFallback>
            </Avatar>
            <Button variant="ghost" size="icon" onClick={logout} title="Log out">
              <LogOut size={14} />
            </Button>
          </div>
        )}
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
```

**Step 2: Also add theme toggle to HomePage**

Update `web-ui/frontend/src/pages/HomePage.tsx` to include a theme toggle and logout in the top-right corner:

Add to the beginning of the `HomePage` component's return, before the title:

```tsx
{/* Top-right controls */}
<div className="fixed right-4 top-4 flex items-center gap-2">
  <Button variant="ghost" size="icon" onClick={toggleTheme}>
    {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
  </Button>
  <Button variant="ghost" size="icon" onClick={logout} title="Log out">
    <LogOut size={14} />
  </Button>
</div>
```

And add the necessary imports and hooks:

```tsx
import { useTheme } from "@/hooks/useTheme";
import { Sun, Moon, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

// Inside component:
const { theme, toggleTheme } = useTheme();
const { user, logout } = useAuth();
```

**Step 3: Verify build**

```bash
cd web-ui/frontend && pnpm run build 2>&1 | tail -5
```

Expected: Build succeeds.

**Step 4: Commit**

```bash
git add web-ui/frontend/src/components/layout/FeatureLayout.tsx \
        web-ui/frontend/src/pages/HomePage.tsx
git commit -m "feat: add theme toggle and user controls to FeatureLayout and HomePage"
```

---

### Task 10: Update AdminUsers Page Guard

The `AdminUsersPage` currently redirects non-admins to `/`. That still works since `/` is now the home page. But verify the redirect logic is correct.

**Files:**
- Verify: `web-ui/frontend/src/pages/AdminUsers.tsx:18-21`

**Step 1: Read and verify**

Read `web-ui/frontend/src/pages/AdminUsers.tsx`. Confirm the redirect target is `/` (which is now HomePage, not ChatPage). This should be fine — no changes needed.

**Step 2: Commit (no-op)**

If no changes needed, skip this commit.

---

### Task 11: Visual Polish and Testing

Start the dev server and verify everything works end-to-end.

**Step 1: Start dev environment**

```bash
./scripts/dev-webui.sh
```

**Step 2: Verify home page**

Open `http://localhost:5173`. Expected:
- See the tile grid with 7 tiles (or 6 if not admin)
- Each tile has a pixel icon and label
- Clicking a tile navigates to the feature
- SNES.css container styling visible on tiles

**Step 3: Verify Chat page**

Click the Chat tile. Expected:
- Navigates to `/chat`
- FeatureLayout shows back arrow + "Chat" title
- WebSocket connects (check browser DevTools Network tab)
- Thread list toggle works
- Can send messages

**Step 4: Verify other feature pages**

Navigate to Knowledge, Graph, Intentions, Games, Settings. Expected:
- Each page shows FeatureLayout with back button + title
- Back button returns to home grid
- No sidebar anywhere
- Theme toggle and logout work

**Step 5: Verify responsive behavior**

Resize browser to mobile width. Expected:
- Grid collapses to 2 columns
- FeatureLayout header still usable
- No sidebar overlay bugs

**Step 6: Fix any visual issues**

Adjust CSS as needed for:
- SNES.css container styling conflicts with Tailwind
- Icon tinting/sizing
- Tile spacing and responsive breakpoints
- Dark mode appearance

**Step 7: Commit any fixes**

```bash
git add -A web-ui/frontend/src/
git commit -m "fix: visual polish for home menu redesign"
```

---

### Task 12: Final Build Verification

**Step 1: Run production build**

```bash
cd web-ui/frontend && pnpm run build 2>&1
```

Expected: `tsc` passes, Vite build succeeds, no warnings about unused imports.

**Step 2: Check for dead imports**

```bash
grep -r "AppLayout\|UnifiedSidebar\|SIDEBAR_KEY\|SidebarOpenButton" web-ui/frontend/src/ \
  --include="*.tsx" --include="*.ts"
```

Expected: No results.

**Step 3: Commit if any cleanup needed**

```bash
git add -u web-ui/frontend/src/
git commit -m "chore: clean up dead imports from sidebar removal"
```
