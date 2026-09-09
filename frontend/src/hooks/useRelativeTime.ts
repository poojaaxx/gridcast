import { useEffect, useState } from "react";

function formatRelative(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

/** Live-updating "N seconds ago" string for a given timestamp, ticking every second. */
export function useRelativeTime(timestamp: number | null): string {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (timestamp === null) return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [timestamp]);

  if (timestamp === null) return "—";
  return formatRelative(Date.now() - timestamp);
}
