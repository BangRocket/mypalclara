import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { AppShell } from "@/components/layout/AppShell";
import { LoginPage } from "@/pages/Login";
import { KnowledgeBasePage } from "@/pages/KnowledgeBase";
import { ChatPage } from "@/pages/Chat";
import { GraphExplorerPage } from "@/pages/GraphExplorer";
import { SettingsPage } from "@/pages/Settings";
import { IntentionsPage } from "@/pages/Intentions";
import { OAuthCallback } from "@/auth/OAuthCallback";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-surface">
        <div className="text-text-muted">Loading...</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback/:provider" element={<OAuthCallback />} />

      {/* Protected */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppShell>
              <Routes>
                <Route path="/" element={<KnowledgeBasePage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/graph" element={<GraphExplorerPage />} />
                <Route path="/intentions" element={<IntentionsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </AppShell>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
