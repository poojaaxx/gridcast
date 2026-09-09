/** Shimmering skeleton placeholders - used instead of plain "Loading..." text. */

export function SkeletonChart({ height = 300 }: { height?: number }) {
  return (
    <div className="w-full animate-in" style={{ height }}>
      <div className="flex h-full items-end gap-2 px-2 pb-6">
        {Array.from({ length: 16 }).map((_, i) => (
          <div
            key={i}
            className="skeleton flex-1 rounded-t-md"
            style={{ height: `${28 + ((i * 37) % 60)}%`, animationDelay: `${i * 40}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="panel p-5 flex flex-col gap-3 animate-in">
      <div className="skeleton h-3 w-20 rounded" />
      <div className="skeleton h-8 w-24 rounded" />
      <div className="skeleton h-3 w-16 rounded" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 px-4 py-3">
      <div className="skeleton h-4 w-28 rounded" />
      <div className="skeleton h-4 w-16 rounded ml-auto" />
      <div className="skeleton h-4 w-16 rounded" />
      <div className="skeleton h-4 w-16 rounded" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-base-700/40 animate-in">
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
}
