import { VIDEO_UPLOAD_LABEL } from '../services/directVideoUpload';

/** One work-based bar for transport, server work and durable publication.
 * The moving highlight signals activity without changing the actual percentage. */
export function VideoUploadProgress({ percent }: { percent?: number }) {
  const value = percent == null ? undefined : Math.max(0, Math.min(99, Math.floor(percent)));
  return <div className="video-upload-progress">
    <div className="video-upload-progress__label">
      <span role="status">{VIDEO_UPLOAD_LABEL}</span>
      <strong>{value == null ? '…' : `${value}٪`}</strong>
    </div>
    <div className="video-upload-progress__track" role="progressbar" aria-label={VIDEO_UPLOAD_LABEL}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
      <div className="video-upload-progress__fill" style={{ width: `${value ?? 0}%` }} />
      <div className="video-upload-progress__activity" aria-hidden="true" />
    </div>
  </div>;
}
