import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { LoginPage } from "@/pages/Login";
import { OAuthCallback } from "@/auth/OAuthCallback";
import { PendingApproval } from "@/pages/PendingApproval";
import { SuspendedPage } from "@/pages/Suspended";

import { AppRegistryProvider } from "@/system/apps/registry";
import { defaultApps } from "@/system/apps/defaultApps";
import { Wallpaper } from "@/system/theme/Wallpaper";
import { Desktop } from "@/system/filesystem/Desktop";
import { WindowSystem } from "@/system/window/WindowSystem";
import { Taskbar } from "@/system/taskbar/Taskbar";
import { ContextMenu } from "@/system/contextmenu/ContextMenu";
import { GlobalEvents } from "@/system/GlobalEvents";
import { useWindowStore } from "@/system/window/store";

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

function ClaraOSDesktop() {
  useEffect(() => {
    const app = defaultApps.get("clara-chat");
    if (app) {
      useWindowStore
        .getState()
        .openWindow(
          "clara-chat",
          "clara-chat",
          app.name,
          app.defaultWindowSize,
          app.icon,
        );
    }
  }, []);

  return (
    <AppRegistryProvider apps={defaultApps}>
      <Wallpaper>
        <Desktop />
        <WindowSystem />
      </Wallpaper>
      <Taskbar />
      <ContextMenu />
      <GlobalEvents />
    </AppRegistryProvider>
  );
}

export function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback/:provider" element={<OAuthCallback />} />
      <Route path="/pending" element={<PendingApproval />} />
      <Route path="/suspended" element={<SuspendedPage />} />

      {/* Protected — ClaraOS desktop */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <ClaraOSDesktop />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
