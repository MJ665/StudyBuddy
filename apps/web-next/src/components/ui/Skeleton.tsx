import React from 'react';
import { cn } from '@/lib/cn';

/**
 * Skeleton loading placeholders.
 *
 * Base `<Skeleton />` renders a themed shimmer block (see the `.skeleton` class
 * in globals.css — respects prefers-reduced-motion). The composites below shape
 * the shimmer to match real content so a loading screen mirrors its final
 * layout instead of a bare spinner. Usage: `if (loading && !data) return <XSkeleton/>`.
 */

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return <div className={cn('skeleton', className)} aria-hidden="true" {...props} />;
}

/** N lines of text; the last line is shorter for realism. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn('h-3.5', i === lines - 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  );
}

export function SkeletonAvatar({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <Skeleton
      className={cn('rounded-full shrink-0', className)}
      style={{ width: size, height: size }}
    />
  );
}

/** A generic content card (title + body lines). */
export function SkeletonCard({ className, lines = 3 }: { className?: string; lines?: number }) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-[var(--color-surface-bright)] bg-[var(--color-surface-container-low)] p-5',
        className,
      )}
    >
      <Skeleton className="h-5 w-1/2 mb-4" />
      <SkeletonText lines={lines} />
    </div>
  );
}

/** A KPI/stat tile: small label + big number. */
export function SkeletonStat({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-[var(--color-surface-bright)] bg-[var(--color-surface-container-low)] p-5',
        className,
      )}
    >
      <Skeleton className="h-3 w-20 mb-3" />
      <Skeleton className="h-8 w-24" />
    </div>
  );
}

/** A vertical list of rows (avatar + two text lines). */
export function SkeletonList({ rows = 5, avatar = true, className }: { rows?: number; avatar?: boolean; className?: string }) {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 rounded-xl border border-[var(--color-surface-bright)] bg-[var(--color-surface-container-low)] p-4"
        >
          {avatar && <SkeletonAvatar size={40} />}
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="h-6 w-12 rounded-lg" />
        </div>
      ))}
    </div>
  );
}

/** A table: header row + N body rows across C columns. */
export function SkeletonTable({ rows = 6, cols = 4, className }: { rows?: number; cols?: number; className?: string }) {
  return (
    <div className={cn('rounded-2xl border border-[var(--color-surface-bright)] overflow-hidden', className)}>
      <div className="flex gap-4 p-4 bg-[var(--color-surface-container)]">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3.5 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 p-4 border-t border-[var(--color-surface-bright)]">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className="h-3.5 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** A chart placeholder (bars of varying height). */
export function SkeletonChart({ className, bars = 8 }: { className?: string; bars?: number }) {
  const heights = ['40%', '65%', '50%', '80%', '55%', '70%', '45%', '90%'];
  return (
    <div
      className={cn(
        'rounded-2xl border border-[var(--color-surface-bright)] bg-[var(--color-surface-container-low)] p-5',
        className,
      )}
    >
      <Skeleton className="h-4 w-32 mb-5" />
      <div className="flex items-end gap-2 h-40">
        {Array.from({ length: bars }).map((_, i) => (
          <Skeleton key={i} className="flex-1 rounded-t-md" style={{ height: heights[i % heights.length] }} />
        ))}
      </div>
    </div>
  );
}

/** A responsive grid of stat tiles — common dashboard header. */
export function SkeletonStatGrid({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn('grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonStat key={i} />
      ))}
    </div>
  );
}
