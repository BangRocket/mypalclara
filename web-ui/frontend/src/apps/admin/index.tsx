import { useAuth } from '@/auth/AuthProvider';
import { AdminUsersPage } from '@/pages/AdminUsers';

export default function AdminApp({ windowId: _windowId }: { windowId: string }) {
  const { user } = useAuth();

  if (user && !user.is_admin) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>You do not have admin access.</p>
      </div>
    );
  }

  return <AdminUsersPage />;
}
