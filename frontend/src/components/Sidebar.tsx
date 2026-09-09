import clsx from "clsx";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Database,
  HeartPulse,
  LayoutDashboard,
  LineChart,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  Zap,
} from "lucide-react";
import { useUI } from "../hooks/useUI";
import Tooltip from "./Tooltip";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/forecasts", label: "Forecast Explorer", icon: LineChart, end: false },
  { to: "/performance", label: "Model Performance", icon: BarChart3, end: false },
  { to: "/data", label: "Data Explorer", icon: Database, end: false },
  { to: "/monitoring", label: "Model Monitoring", icon: HeartPulse, end: false },
];

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebarCollapsed, mobileNavOpen, setMobileNavOpen } = useUI();

  return (
    <>
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-base-700/60 bg-base-900 transition-transform duration-200 md:static md:translate-x-0",
          sidebarCollapsed ? "md:w-[76px]" : "md:w-60",
          mobileNavOpen ? "translate-x-0 animate-slideInLeft" : "-translate-x-full"
        )}
      >
        <div className="flex items-center gap-2.5 px-5 h-16 border-b border-base-700/60 flex-shrink-0">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 flex items-center justify-center flex-shrink-0 shadow-glow">
            <Zap className="h-4.5 w-4.5 text-base-950" fill="currentColor" strokeWidth={1} />
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <p className="font-bold text-slate-100 text-sm leading-none tracking-tight">GridCast</p>
              <p className="text-2xs text-slate-500 mt-1 truncate">Energy Intelligence</p>
            </div>
          )}
          <button
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation"
            className="btn-icon ml-auto md:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto no-scrollbar">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={sidebarCollapsed ? label : undefined}
              className={({ isActive }) =>
                clsx("nav-item", isActive ? "nav-item-active" : "nav-item-inactive", sidebarCollapsed && "md:justify-center md:px-2")
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-accent-400" aria-hidden="true" />
                  )}
                  <Icon className="h-[18px] w-[18px] flex-shrink-0" aria-hidden="true" />
                  <span className={clsx("truncate", sidebarCollapsed && "md:sr-only")}>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-3 border-t border-base-700/60 flex-shrink-0">
          <Tooltip label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} side="top" className="flex w-full">
            <button
              onClick={toggleSidebarCollapsed}
              aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              className={clsx("nav-item nav-item-inactive w-full hidden md:flex", sidebarCollapsed && "justify-center px-2")}
            >
              {sidebarCollapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
              {!sidebarCollapsed && <span>Collapse</span>}
            </button>
          </Tooltip>
          {!sidebarCollapsed && (
            <p className="text-2xs text-slate-600 leading-relaxed px-3 pt-3">
              GridCast v2.0 · Continuous forecast evaluation
            </p>
          )}
        </div>
      </aside>
    </>
  );
}

