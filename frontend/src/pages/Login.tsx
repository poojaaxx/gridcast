import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { AlertCircle, Eye, EyeOff, Loader2, Zap } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";

export default function Login() {
  const { isAuthenticated, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!authLoading && isAuthenticated) {
    const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname;
    return <Navigate to={from ?? "/"} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname;
      navigate(from ?? "/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Invalid username or password.");
      } else if (err instanceof ApiError && err.status === 429) {
        setError("Too many failed attempts. Please wait a few minutes before trying again.");
      } else {
        setError("Unable to reach the authentication service. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell flex min-h-screen w-full items-center justify-center px-4">
      <div className="w-full max-w-sm animate-in">
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-accent-400 to-accent-600 flex items-center justify-center shadow-glow">
            <Zap className="h-6 w-6 text-base-950" fill="currentColor" strokeWidth={1} />
          </div>
          <div className="text-center">
            <p className="font-bold text-slate-100 text-lg leading-none tracking-tight">GridCast</p>
            <p className="text-xs text-slate-500 mt-1.5">Energy Intelligence Platform</p>
          </div>
        </div>

        <div className="panel p-6 shadow-elevated">
          <h1 className="text-sm font-semibold text-slate-200 mb-0.5">Sign in</h1>
          <p className="text-xs text-slate-500 mb-6">
            Sign in to access the GridCast dashboard and forecasting tools.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="username" className="block text-2xs font-semibold uppercase tracking-widest text-slate-500 mb-1.5">
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-lg border border-base-700 bg-base-850 px-3 py-2 text-sm text-slate-200 transition-colors placeholder:text-slate-600 hover:border-base-600 focus:outline-none focus:ring-1 focus:ring-accent-500/50"
                placeholder="admin"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-2xs font-semibold uppercase tracking-widest text-slate-500 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-base-700 bg-base-850 px-3 py-2 pr-10 text-sm text-slate-200 transition-colors placeholder:text-slate-600 hover:border-base-600 focus:outline-none focus:ring-1 focus:ring-accent-500/50"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger-500/20 bg-danger-500/10 px-3 py-2.5 text-xs text-danger-400">
                <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={submitting} className="btn-primary w-full py-2.5">
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-2xs text-slate-600 mt-6">
          Access to the Admin Console is limited to operator accounts with admin privileges.
        </p>
      </div>
    </div>
  );
}
