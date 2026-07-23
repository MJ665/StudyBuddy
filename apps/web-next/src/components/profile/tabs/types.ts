/** Superset context passed from UserProfile to its tab components.
 *  Loosely typed on purpose: the extraction moved JSX verbatim; field
 *  tightening happens with the typed-hooks migration. */
export type ProfileTabCtx = Record<string, any>;
