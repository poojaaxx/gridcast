import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LogOut, Menu, RefreshCw, ShieldCheck } from "lucide-react";
import { api } from "../services/api";
import { useUI } from "../hooks/useUI";
import { useAuth } from "../hooks/useAuth";
import { useRelativeTime } from "../hooks/useRelativeTime";
import RegionSelector from "./RegionSelector";
import StatusBadge from "./StatusBadge";

interface Props {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
  lastUpdated?: number | null;
}

export default function Topbar({ title, subtitle, onRefresh, refreshing, lastUpdated = null }: Props) {
  const { setMobileNavOpen } = useUI();
  const { user, isAuthenticated, logout } = useAuth();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [dataMode, setDataMode] = useState<"live" | "demo" | null>(null);
  const updatedLabel = useRelativeTime(lastUpdated);

  useEffect(() => {
    let mounted = true;
    const check = () =>
      api
        .health()
        .then((res) => {
          if (!mounted) return;
          setConnected(true);
          setDataMode(res.data_mode);
        })
        .catch(() => mounted && setConnected(false));
    check();
    const interval = setInterval(check, 30_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="flex h-16 flex-shrink-0 items-center justify-between gap-3 border-b border-base-700/60 bg-base-900/80 backdrop-blur px-4 md:px-6">
      <div className="flex items-center gap-3 min-w-0">
        <button onClick={() => setMobileNavOpen(true)} aria-label="Open navigation" className="btn-icon md:hidden">
          <Menu className="h-5 w-5" />
        </button>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="page-title truncate">{title}</h1>
            {dataMode && <StatusBadge status={dataMode === "demo" ? "warning" : "healthy"} label={dataMode === "demo" ? "Demo Data" : "Live Data"} />}
          </div>
          {subtitle && <p className="page-subtitle truncate">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-4 flex-shrink-0">
        <div className="hidden sm:flex items-center gap-1.5 text-2xs text-slate-500 pr-1" title={connected ? "API reachable" : "API unreachable"}>
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              connected === null ? "bg-slate-600" : connected ? "bg-success-500 animate-pulseDot" : "bg-danger-500"
            }`}
            aria-hidden="true"
          />
          <span className="font-semibold uppercase tracking-wide">
            {connected === null ? "Checking" : connected ? "Live" : "Offline"}
          </span>
          {lastUpdated !== null && <span className="text-slate-600">· Updated {updatedLabel}</span>}
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Refresh data"
            className="btn-secondary px-3 py-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">{refreshing ? "Refreshing…" : "Refresh"}</span>
          </button>
        )}

        <RegionSelector />

        <div className="h-6 w-px bg-base-700 hidden sm:block" />

        {isAuthenticated && user ? (
          <div className="flex items-center gap-2">
            <span className="hidden md:inline-flex items-center gap-1.5 text-xs text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 text-accent-400" />
              {user.username}
            </span>
            <button onClick={() => logout()} aria-label="Sign out" className="btn-secondary px-3 py-1.5">
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        ) : (
          <Link to="/login" className="btn-secondary px-3 py-1.5">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Sign in</span>
          </Link>
        )}
      </div>
    </header>
  );
}
