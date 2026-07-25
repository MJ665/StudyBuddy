'use client';

import React, { useEffect, useState } from 'react';
import { Activity, Clock, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useQuery } from '@tanstack/react-query';

export default function SystemHealthMonitor() {
  const { data: taskData, isLoading, refetch } = useQuery({
    queryKey: ['system-task-status'],
    queryFn: async () => {
      return ApiService.getAllTaskStatus();
    },
    refetchInterval: 10000 // Auto-poll every 10s
  });

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-zinc-800 rounded w-1/4"></div>
        <div className="h-64 bg-zinc-800 rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="w-6 h-6 text-emerald-400" />
            System Background Telemetry
          </h2>
          <p className="text-zinc-400 text-sm mt-1">Live monitoring of async worker tasks and system crons.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500 font-medium">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          Live Polling Active
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-x-auto shadow-xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-zinc-950/50 border-b border-zinc-800 text-zinc-400 text-xs uppercase tracking-widest font-bold">
              <th className="p-4">Task Definition</th>
              <th className="p-4">Status</th>
              <th className="p-4">Last Executed</th>
              <th className="p-4 text-right">Total Runs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {!taskData || taskData.length === 0 ? (
              <tr>
                <td colSpan={4} className="p-8 text-center text-zinc-500 text-sm">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  No telemetry data received from the engine yet.
                </td>
              </tr>
            ) : (
              taskData.map((task: any, i: number) => (
                <tr key={i} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="p-4">
                    <span className="text-white font-medium block">{task.task_name}</span>
                    <span className="text-xs text-zinc-500 block mt-0.5">{task.worker_id || 'system-cron'}</span>
                  </td>
                  <td className="p-4">
                    {task.status === 'success' ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Healthy
                      </span>
                    ) : (task.status === 'failed' || task.status === 'failure') ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-red-500/10 text-red-400 text-xs font-semibold">
                        <XCircle className="w-3.5 h-3.5" /> Failed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-500/10 text-zinc-400 text-xs font-semibold">
                        <Clock className="w-3.5 h-3.5" /> Idle
                      </span>
                    )}
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-zinc-300 text-sm">
                      <Clock className="w-4 h-4 text-zinc-500" />
                      {task.executed_at ? new Date(task.executed_at).toLocaleString() : 'Never'}
                    </div>
                  </td>
                  <td className="p-4 text-right text-zinc-300 text-sm font-mono">
                    {task.runs ?? 0}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
