import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import LoadingState from "./LoadingState";

/** Guards a route behind "must be logged in" (and optionally "must be
 * admin"). This is a UX convenience only - every sensitive operation is
 * independently enforced by the backend regardless of what this component
 * does, so a user can never bypass real authorization by tampering with the
 * frontend. */
export default function ProtectedRoute({ children, requireAdmin = false }: { children: ReactNode; requireAdmin?: boolean }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-base-950">
        <LoadingState label="Checking session…" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (requireAdmin && !isAdmin) {
    return <Unauthorized />;
  }

  return <>{children}</>;
}

/** A real 403 experience, not a silent redirect - an authenticated non-admin
 * who navigates to /admin needs to understand why they can't get in. */
function Unauthorized() {
  return (
    <div className="flex h-screen w-full flex-col items-center justify-center gap-4 bg-base-950 app-shell text-center px-6">
      <div className="rounded-full bg-danger-500/10 p-4">
        <ShieldAlert className="h-8 w-8 text-danger-400" aria-hidden="true" />
      </div>
      <div>
        <h1 className="page-title text-xl">403 — Access denied</h1>
        <p className="page-subtitle mt-2 max-w-sm mx-auto">
          Your account doesn't have admin privileges. The Admin Console is restricted to operators who manage
          ingestion, training, forecasting, and evaluation.
        </p>
      </div>
      <a href="/" className="btn-secondary px-4 py-2 mt-2">
        Back to dashboard
      </a>
    </div>
  );
}
