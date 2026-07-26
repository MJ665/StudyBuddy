'use client';

// The /exams routes (list, [id]/review) render BankCreationModal + other
// components that call useToast(). This standalone route group has no (app)/
// (public) layout, so it must provide its own ToastProvider.
import { ToastProvider } from '@/components/ui/Toast';

export default function ExamsLayout({ children }: { children: React.ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}
