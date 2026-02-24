import { useEffect } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useAuth } from '@/auth/AuthProvider';
import { ChatRuntimeProvider } from '@/components/chat/ChatRuntimeProvider';
import { ChatPage } from '@/pages/Chat';

export default function ClaraChatApp({ windowId: _windowId }: { windowId: string }) {
  const { user } = useAuth();
  const connected = useChatStore((s) => s.connected);

  useEffect(() => {
    if (user && !connected) {
      const token = sessionStorage.getItem('token') || '';
      useChatStore.getState().connect(token);
    }
  }, [user, connected]);

  if (!user) return null;

  return (
    <ChatRuntimeProvider>
      <ChatPage />
    </ChatRuntimeProvider>
  );
}
