'use client';

import { useRouter } from 'next/navigation';
import ResourceCenter from '@/components/resources/ResourceCenter';
import { useSessionStore } from '@/stores/sessionStore';

export default function ResourcesPage() {
  const router = useRouter();
  const { user } = useSessionStore();
  return (
    <ResourceCenter
      user={user}
      group={{ id: user?.group_id, name: user?.group_name || 'Your Group' }}
      onBack={() => router.push('/dashboard')}
    />
  );
}
