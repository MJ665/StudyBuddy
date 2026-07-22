'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

// White-label branding: every surface reads brand from here so an org's portal
// shows "OrgLogo × StudyBuddy" and "Powered by StudyBuddy" consistently.
// Org branding is stashed in localStorage at login (key: org_branding); the
// parent brand (StudyBuddy) is always present.

export interface Branding {
  brandName: string;      // org brand name (defaults to StudyBuddy)
  orgLogoUrl?: string | null;
}

const DEFAULT: Branding = { brandName: 'StudyBuddy', orgLogoUrl: null };
const BrandingContext = createContext<Branding>(DEFAULT);

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<Branding>(DEFAULT);
  useEffect(() => {
    try {
      const raw = localStorage.getItem('org_branding');
      if (raw) {
        const b = JSON.parse(raw);
        setBranding({ brandName: b.brand_name || 'StudyBuddy', orgLogoUrl: b.logo_url || null });
      }
    } catch {
      /* keep defaults */
    }
  }, []);
  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>;
}

export function useBranding(): Branding {
  return useContext(BrandingContext);
}

/** Co-brand header: OrgLogo × StudyBuddy. */
export function CoBrand({ className = '' }: { className?: string }) {
  const { brandName, orgLogoUrl } = useBranding();
  const isOrg = brandName && brandName !== 'StudyBuddy';
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {orgLogoUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={orgLogoUrl} alt="" className="h-7 w-auto rounded" />
      )}
      {isOrg && <span className="font-bold">{brandName}</span>}
      {isOrg && <span className="text-slate-500">×</span>}
      <span className="font-black text-emerald-400">StudyBuddy</span>
    </div>
  );
}

/** Universal footer. */
export function PoweredByStudyBuddy({ className = '' }: { className?: string }) {
  return (
    <p className={`text-center text-slate-600 text-xs ${className}`}>Powered by StudyBuddy</p>
  );
}
