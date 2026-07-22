'use client';

import { useRouter } from 'next/navigation';
import ForgotPasswordPage from '@/components/auth/ForgotPasswordPage';

export default function ForgotPasswordRoute() {
  const router = useRouter();
  return (
    <ForgotPasswordPage
      onBack={() => router.push('/login')}
      onSuccess={(email: string, groupId: number) =>
        router.push(
          `/reset-password?email=${encodeURIComponent(email)}&groupId=${groupId}`,
        )
      }
    />
  );
}
