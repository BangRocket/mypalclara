import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { admin, type AdminUser } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type StatusFilter = "all" | "pending" | "active" | "suspended";

export function AdminUsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Redirect non-admins
  if (user && !user.is_admin) {
    return <Navigate to="/" replace />;
  }

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const params: { status?: string } = {};
      if (filter !== "all") params.status = filter;
      const res = await admin.users(params);
      setUsers(res.users);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to fetch users:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [filter]);

  const handleApprove = async (userId: string) => {
    setActionLoading(userId);
    try {
      await admin.approve(userId);
      await fetchUsers();
    } catch (err) {
      console.error("Failed to approve user:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSuspend = async (userId: string) => {
    setActionLoading(userId);
    try {
      await admin.suspend(userId);
      await fetchUsers();
    } catch (err) {
      console.error("Failed to suspend user:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const statusBadge = (status: string | undefined) => {
    const s = status || "active";
    switch (s) {
      case "pending":
        return <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30">Pending</Badge>;
      case "active":
        return <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Active</Badge>;
      case "suspended":
        return <Badge variant="destructive">Suspended</Badge>;
      default:
        return <Badge variant="outline">{s}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">User Management</h1>
          <p className="text-sm text-muted-foreground mt-1">{total} total users</p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {(["all", "pending", "active", "suspended"] as StatusFilter[]).map((f) => (
          <Button
            key={f}
            variant={filter === f ? "secondary" : "ghost"}
            onClick={() => setFilter(f)}
            className="capitalize"
          >
            {f}
          </Button>
        ))}
      </div>

      {/* Users list */}
      {loading ? (
        <div className="text-muted-foreground text-center py-12">Loading users...</div>
      ) : users.length === 0 ? (
        <div className="text-muted-foreground text-center py-12">
          No {filter === "all" ? "" : filter} users found.
        </div>
      ) : (
        <div className="border border-border rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-muted border-b border-border">
                <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">User</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Email</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Platforms</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Status</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Joined</th>
                <th className="text-right text-xs font-medium text-muted-foreground px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-border last:border-b-0 hover:bg-muted/50 transition">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {u.avatar_url ? (
                        <img src={u.avatar_url} alt="" className="w-8 h-8 rounded-full" />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">
                          {u.display_name?.[0]?.toUpperCase() || "?"}
                        </div>
                      )}
                      <div>
                        <span className="text-sm font-medium">{u.display_name}</span>
                        {u.is_admin && (
                          <Badge variant="outline" className="ml-2 text-[10px] px-1.5 py-0">
                            Admin
                          </Badge>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{u.email || "--"}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 flex-wrap">
                      {u.platforms?.map((p, i) => (
                        <Badge key={i} variant="secondary" className="text-[10px]">
                          {p.platform}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">{statusBadge(u.status)}</td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "--"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      {u.status === "pending" && (
                        <Button
                          size="xs"
                          onClick={() => handleApprove(u.id)}
                          disabled={actionLoading === u.id}
                        >
                          {actionLoading === u.id ? "..." : "Approve"}
                        </Button>
                      )}
                      {u.status === "suspended" && (
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => handleApprove(u.id)}
                          disabled={actionLoading === u.id}
                        >
                          {actionLoading === u.id ? "..." : "Reactivate"}
                        </Button>
                      )}
                      {u.status === "active" && u.id !== user?.id && (
                        <Button
                          size="xs"
                          variant="destructive"
                          onClick={() => handleSuspend(u.id)}
                          disabled={actionLoading === u.id}
                        >
                          {actionLoading === u.id ? "..." : "Suspend"}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
