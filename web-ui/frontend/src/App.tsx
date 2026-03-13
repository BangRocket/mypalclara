import { Routes, Route } from "react-router-dom";
import { useAuth, RedirectToSignIn } from "@clerk/react";
import { AppLayout } from "@/components/layout/AppLayout";
import { ChatRuntimeProvider } from "@/components/chat/ChatRuntimeProvider";
import { KnowledgeBasePage } from "@/pages/KnowledgeBase";
import { ChatPage } from "@/pages/Chat";
import { SettingsPage } from "@/pages/Settings";

export function App() {
  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!isSignedIn) {
    return <RedirectToSignIn />;
  }

  return (
    <ChatRuntimeProvider>
      <AppLayout>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/knowledge" element={<KnowledgeBasePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </AppLayout>
    </ChatRuntimeProvider>
  );
}
