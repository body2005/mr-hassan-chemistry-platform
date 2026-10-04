// Binary units, identical to the API. Extract retains its separate 50 MiB cap.
export const MAX_VIDEO_BYTES = 5 * 1024 ** 3;
export const MAX_MATERIAL_BYTES = 1024 ** 3;
export function validateLessonUpload(file: File, kind: "video" | "material"): void {
  const limit = kind === "video" ? MAX_VIDEO_BYTES : MAX_MATERIAL_BYTES;
  if (file.size > limit) throw new Error(`حد الملف ${limit.toLocaleString("en-US")} بايت (${kind === "video" ? "5" : "1"} GiB).`);
}
