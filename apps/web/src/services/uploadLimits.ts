// Binary units, identical to the API. Extract retains its separate 50 MiB cap.
export const MAX_VIDEO_BYTES = 5 * 1024 ** 3;
export const MAX_MATERIAL_BYTES = 1024 ** 3;
export const MAX_LESSON_TITLE_LENGTH = 1000;
export const MAX_VIDEO_FILENAME_LENGTH = 1000;
export function validateLessonTitle(title: string, lang = 'ar'): void {
  const length = [...title.trim()].length;
  if (length < 2 || length > MAX_LESSON_TITLE_LENGTH) {
    throw new Error(lang === 'ar'
      ? `عنوان الدرس يجب أن يكون من حرفين إلى ${MAX_LESSON_TITLE_LENGTH} حرف. النص محفوظ؛ عدّله ثم أعد المحاولة.`
      : `Lesson titles must contain 2–${MAX_LESSON_TITLE_LENGTH} characters. Your text is kept; edit it and retry.`);
  }
}
export function validateLessonUpload(file: File, kind: "video" | "material"): void {
  if (kind === 'video' && [...file.name].length > MAX_VIDEO_FILENAME_LENGTH) {
    throw new Error(`اسم ملف الفيديو أطول من ${MAX_VIDEO_FILENAME_LENGTH} حرف. اختصر اسم الملف ثم أعد اختياره.`);
  }
  const limit = kind === "video" ? MAX_VIDEO_BYTES : MAX_MATERIAL_BYTES;
  if (file.size > limit) throw new Error(`حد الملف ${limit.toLocaleString("en-US")} بايت (${kind === "video" ? "5" : "1"} GiB).`);
}
