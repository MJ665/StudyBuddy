'use client';

import { useRouter } from 'next/navigation';
import UserProfile from '@/components/profile/UserProfile';
import { useSessionStore } from '@/stores/sessionStore';

export default function MyProfilePage() {
  const router = useRouter();
  const { user } = useSessionStore();
  return (
    <UserProfile
      isOwnProfile={true}
      slug={user?.email?.split('@')[0]}
      onBack={() => router.push('/dashboard')}
    />
  );
}
