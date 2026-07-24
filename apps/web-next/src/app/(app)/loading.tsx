import { Skeleton, SkeletonStatGrid, SkeletonCard } from '@/components/ui/Skeleton';

/**
 * Route-segment loading skeleton for the authenticated app shell. Shown by
 * Next.js during (app) route transitions / RSC streaming, so navigation feels
 * instant instead of blank.
 */
export default function AppLoading() {
  return (
    <div className="min-h-screen bg-[var(--color-surface-dim)] p-4 sm:p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
        <SkeletonStatGrid count={4} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <SkeletonCard className="lg:col-span-2" lines={4} />
          <SkeletonCard lines={3} />
        </div>
      </div>
    </div>
  );
}
