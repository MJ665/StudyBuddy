'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import ExecutiveReport from '@/components/dashboard/ExecutiveReport';

export default function BatchReportPage({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const router = useRouter();
  const { batchId } = use(params);
  return (
    <ExecutiveReport
      batchId={Number(batchId)}
      onBack={() => router.push('/admin')}
    />
  );
}
