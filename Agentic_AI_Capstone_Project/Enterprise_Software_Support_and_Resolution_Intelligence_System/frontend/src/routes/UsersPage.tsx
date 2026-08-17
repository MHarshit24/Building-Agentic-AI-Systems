import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { createUser, deactivateUser, listUsers, reactivateUser, updateUser } from "../api/endpoints";
import type { UserRole } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { useAuthStore } from "../store/authStore";

function extractErrorDetail(err: unknown, fallback: string): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

interface CreateUserFormProps {
  onCreated: () => void;
}

function CreateUserForm({ onCreated }: CreateUserFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("support_agent");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createUser({ email, password, role }),
    onSuccess: () => {
      setEmail("");
      setPassword("");
      setError(null);
      onCreated();
    },
    onError: (err) => setError(extractErrorDetail(err, "Something went wrong creating this user.")),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
      className="mt-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <Input
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        className="min-w-55"
      />
      <Input
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={8}
      />
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Role</label>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        >
          <option value="support_agent">Support Agent</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? <Spinner /> : "Create"}
      </Button>
      {error && <p className="w-full text-sm text-red-600 dark:text-red-400">{error}</p>}
    </form>
  );
}

export default function UsersPage() {
  const queryClient = useQueryClient();
  const currentUserId = useAuthStore((s) => s.userId);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery({ queryKey: ["users"], queryFn: () => listUsers({ limit: 100 }) });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: UserRole }) => updateUser(userId, { role }),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (err) => setActionError(extractErrorDetail(err, "Couldn't change that user's role.")),
  });
  const deactivateMutation = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (err) => setActionError(extractErrorDetail(err, "Couldn't deactivate that user.")),
  });
  const reactivateMutation = useMutation({ mutationFn: reactivateUser, onSuccess: invalidate });

  const anyPending = roleMutation.isPending || deactivateMutation.isPending || reactivateMutation.isPending;

  return (
    <div className="scroll-thin h-full overflow-y-auto bg-slate-50 px-8 py-6 dark:bg-slate-950">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">Users</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Everyone who has signed up or been created, and their role.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreate((v) => !v)}>
          {showCreate ? "Cancel" : "New user"}
        </Button>
      </div>

      {showCreate && (
        <CreateUserForm
          onCreated={() => {
            invalidate();
            setShowCreate(false);
          }}
        />
      )}

      {actionError && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{actionError}</p>}

      {isLoading ? (
        <div className="mt-8 flex justify-center text-slate-400">
          <Spinner size={24} />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Last login</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {data?.users.map((u) => {
                const isSelf = u.user_id === currentUserId;
                return (
                  <tr key={u.user_id}>
                    <td className="px-4 py-2 text-slate-800 dark:text-slate-100">
                      {u.email} {isSelf && <span className="text-xs text-slate-400">(you)</span>}
                    </td>
                    <td className="px-4 py-2">
                      <select
                        value={u.role}
                        disabled={isSelf || anyPending}
                        onChange={(e) => roleMutation.mutate({ userId: u.user_id, role: e.target.value as UserRole })}
                        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                      >
                        <option value="support_agent">Support Agent</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-2">
                      <Badge tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Deactivated"}</Badge>
                    </td>
                    <td className="px-4 py-2 text-slate-500 dark:text-slate-400">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {u.is_active ? (
                        <button
                          type="button"
                          disabled={isSelf || anyPending}
                          onClick={() => deactivateMutation.mutate(u.user_id)}
                          className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-900/20"
                        >
                          Deactivate
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={anyPending}
                          onClick={() => reactivateMutation.mutate(u.user_id)}
                          className="rounded px-2 py-1 text-xs text-green-600 hover:bg-green-50 disabled:opacity-50 dark:hover:bg-green-900/20"
                        >
                          Reactivate
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
