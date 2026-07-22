'use client';

import { useRouter } from 'next/navigation';
import DiscussionForum from '@/components/dashboard/DiscussionForum';
import { useSessionStore } from '@/stores/sessionStore';

export default function DiscussionsPage() {
  const router = useRouter();
  const { user } = useSessionStore();
  return (
    <DiscussionForum
      user={user}
      onViewProfile={(slug: string) => router.push(`/profile/${slug}`)}
      onBack={() => router.push('/dashboard')}
    />
  );
}
