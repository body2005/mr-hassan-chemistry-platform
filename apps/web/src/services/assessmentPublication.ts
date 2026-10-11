import type { GeneratedQuestion } from '../types/quiz';
import { canonicalQuestionType } from './questionType';
import { hasContentReview } from './quizContentReview';
import { canonicalEditorOptionKey } from './mcqOptions';

export type EditorStage = 'setup' | 'review' | 'publish';
export interface PublicationInput {
  title: string; lessonId?: string; isQuiz: boolean; duration: string | number;
  startDate: string; startTime: string; endDate: string; endTime: string;
  questions: GeneratedQuestion[];
}
export function validateAssessmentPublication(input: PublicationInput): { message: string; stage: EditorStage } | null {
  const noun = input.isQuiz ? 'الاختبار' : 'الواجب';
  const failure = (message: string, stage: EditorStage) => ({ message, stage });
  if (!input.title.trim()) return failure(`يرجى إدخال اسم ${noun} أولاً (يلزم ادخاله).`, 'setup');
  if (!input.lessonId) return failure(`يرجى اختيار الدرس المرتبط ${input.isQuiz ? 'بالاختبار' : 'بالواجب'} (يلزم ادخاله).`, 'setup');
  if (input.questions.length === 0) return failure(`لا يمكن حفظ أو رفع ${noun} وهو فارغ. يرجى إضافة سؤال واحد على الأقل أولاً.`, 'review');
  for (const [index, question] of input.questions.entries()) {
    const prefix = `السؤال ${index + 1}: `;
    const type = canonicalQuestionType(question.question_type);
    if (type === 'unknown') return failure(prefix + 'نوع غير محدد. اختر نوع السؤال قبل النشر.', 'review');
    if (question.question_text.trim().length < 2 || question.question_text.length > 10000) return failure(prefix + 'أدخل نص السؤال كاملاً، في حدود 10000 حرف.', 'review');
    if (!Number.isFinite(question.points) || Number(question.points) <= 0 || Number(question.points) > 1000) return failure(prefix + 'حدد درجة موجبة لا تتجاوز 1000.', 'review');
    if (!hasContentReview(question)) return failure(prefix + 'يلزم مراجعة النص والاختيارات مع الملف الأصلي قبل النشر.', 'review');
    if (type === 'multiple_choice') {
      const options = question.options ?? [];
      const keys = options.map(option => canonicalEditorOptionKey(option.key));
      if (options.length < 2 || options.length > 26 || new Set(keys).size !== keys.length || keys.some(key => !/^[A-Z]$/.test(key)) || options.some(option => !option.text.trim())) {
        return failure(prefix + 'أدخل من اختيارين إلى 26 اختيارًا بمفاتيح فريدة ونصوص غير فارغة.', 'review');
      }
      if (input.isQuiz && options.filter(option => option.is_correct).length !== 1) return failure(prefix + 'حدد إجابة صحيحة واحدة للاختيار من متعدد.', 'review');
    }
    if (input.isQuiz && type === 'true_false' && !question.options?.some(option => option.is_correct) && !question.correct_answer?.trim()) return failure(prefix + 'حدد الإجابة الصحيحة لسؤال صح أو خطأ.', 'review');
    if (input.isQuiz && ['fill_in_blank', 'ordering', 'matching'].includes(type) && !question.correct_answer?.trim()) return failure(prefix + 'حدد الإجابة الصحيحة قبل النشر.', 'review');
  }
  if (input.isQuiz && (!Number.isFinite(Number(input.duration)) || Number(input.duration) <= 0 || Number(input.duration) > 300)) return failure('يرجى تحديد مدة حل الاختبار من 1 إلى 300 دقيقة (يلزم ادخاله).', 'publish');
  if (!input.startDate || !input.startTime.trim()) return failure('يرجى تحديد موعد النشر وبدء الإتاحة (يلزم ادخاله).', 'publish');
  if (!input.endDate || !input.endTime.trim()) return failure(`يرجى تحديد موعد انتهاء الإتاحة وإغلاق ${noun} (يلزم ادخاله).`, 'publish');
  return null;
}
