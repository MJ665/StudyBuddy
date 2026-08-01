import ApiService from '@/services/ApiService';

/**
 * Upload a proctoring artifact (webcam video chunk or snapshot) to S3 via a
 * presigned POST, then log a proctor-event referencing the S3 key.
 *
 * Falls back to logging a base64 data-URL directly when S3 is not configured
 * (e.g. local/dev) so proctoring still records something. Snapshots are small;
 * video chunks are skipped in the fallback (too large for the DB).
 */
export async function uploadProctorMedia(
  attemptId: number,
  blob: Blob,
  opts: { eventType: 'webcam_snapshot' | 'video_chunk'; filename: string; detail?: string },
): Promise<boolean> {
  try {
    const res = (await ApiService.getProctorMediaUploadUrl(
      attemptId,
      opts.filename,
      blob.type || 'application/octet-stream',
    )) as { upload_url: { url: string; fields: Record<string, string> }; s3_key: string };

    const form = new FormData();
    Object.entries(res.upload_url.fields).forEach(([k, v]) => form.append(k, v));
    form.append('file', blob, opts.filename);

    const up = await fetch(res.upload_url.url, { method: 'POST', body: form });
    if (!up.ok) throw new Error(`S3 upload failed (${up.status})`);

    await ApiService.logProctorEvent(attemptId, opts.eventType, opts.detail, res.s3_key);
    return true;
  } catch {
    // S3 unavailable — fall back to an inline data-URL for snapshots only.
    if (opts.eventType === 'webcam_snapshot') {
      try {
        const dataUrl = await blobToDataUrl(blob);
        await ApiService.logProctorEvent(attemptId, 'webcam_snapshot', opts.detail, dataUrl);
        return true;
      } catch {
        return false;
      }
    }
    return false;
  }
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = reject;
    r.readAsDataURL(blob);
  });
}
