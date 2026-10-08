import { AlertCircle, CheckSquare, Loader2, UploadCloud, X } from 'lucide-react';
import { AccessibleDialog } from './AccessibleDialog';
import { clockLabel } from '../services/clockField';
import './QuizPublishConfirmation.css';

export type QuizPublishConfirmationProps = {
  assessmentType: 'quiz' | 'assignment';
  title: string;
  academicYear: '1st_secondary' | '2nd_secondary' | '3rd_secondary';
  questionCount: number;
  totalPoints: number;
  startDate: string;
  startTime: string;
  deadlineDate: string;
  deadlineTime: string;
  durationMinutes: number | '';
  notifyStudents: boolean;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

const academicYears = {
  '1st_secondary': 'الصف الأول الثانوي',
  '2nd_secondary': 'الصف الثاني الثانوي',
  '3rd_secondary': 'الصف الثالث الثانوي',
};

// Presentation only: validation, persistence and publication remain in the
// existing lifecycle. Never derive or mutate a draft inside this dialog.
export function QuizPublishConfirmation(props: QuizPublishConfirmationProps) {
  const quiz = props.assessmentType === 'quiz';
  const label = quiz ? 'الاختبار' : 'الواجب';
  const accent = quiz ? '#0f766e' : '#0f392b';
  return <AccessibleDialog className="modal-overlay publish-confirm-overlay" labelledBy="quiz-publish-heading"
    locked={props.busy} onClose={props.onCancel}>
    <section className="publish-confirm-card" dir="rtl" aria-busy={props.busy}>
      <header className="publish-confirm-header" style={{ background: accent }}>
        <div><UploadCloud size={20} color="#34d399" aria-hidden="true" />
          <h3 id="quiz-publish-heading">تأكيد رفع واعتماد {label}</h3></div>
        <button type="button" className="modal-close-btn publish-confirm-close" aria-label="إغلاق تأكيد النشر"
          disabled={props.busy} onClick={props.onCancel}><X size={18} aria-hidden="true" /></button>
      </header>
      <div className="publish-confirm-body">
        <div className="publish-confirm-intro">
          <AlertCircle size={22} color="var(--success-text)" aria-hidden="true" />
          <div><p>هل أنت متأكد من رغبتك في رفع واعتماد هذا {label} للطلاب؟</p>
            <p>سيتم تثبيت الموعد في جدول التقويم {props.notifyStudents ? 'وإرسال إشعار فوري لجميع طلاب الصف.' : 'وفقاً للإعدادات المحددة.'}</p></div>
        </div>
        {props.error && <p className="publish-confirm-error" role="alert">{props.error}</p>}
        <dl className="publish-confirm-summary">
          <div><dt>العنوان:</dt><dd>{props.title.trim() || `${quiz ? 'اختبار' : 'واجب'} جديد`}</dd></div>
          <div><dt>الصف الدراسي:</dt><dd className="publish-confirm-success">{academicYears[props.academicYear]}</dd></div>
          <div><dt>عدد الأسئلة والدرجات:</dt><dd>{props.questionCount} سؤال ({props.totalPoints} درجة)</dd></div>
          <div><dt>موعد البدء والنشر:</dt><dd dir="ltr" className="publish-confirm-time">{props.startDate} ({clockLabel(props.startTime)})</dd></div>
          <div><dt>{quiz ? 'موعد الإغلاق' : 'آخر موعد للتسليم'}:</dt><dd dir="ltr" className="publish-confirm-time publish-confirm-deadline">{props.deadlineDate} ({clockLabel(props.deadlineTime)})</dd></div>
          {quiz && <div><dt>مدة حل الاختبار:</dt><dd>{props.durationMinutes} دقيقة</dd></div>}
          <div><dt>إشعار الطلاب:</dt><dd className={props.notifyStudents ? 'publish-confirm-success' : ''}>{props.notifyStudents ? '✓ سيتم إرسال إشعار فوري' : 'بدون إشعار'}</dd></div>
        </dl>
      </div>
      <footer className="publish-confirm-footer">
        <button type="button" className="publish-confirm-cancel" disabled={props.busy} onClick={props.onCancel}>إلغاء</button>
        <button type="button" className="publish-confirm-submit" style={{ background: accent }} disabled={props.busy} onClick={props.onConfirm}>
          {props.busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <CheckSquare size={16} aria-hidden="true" />}
          <span>{props.busy ? 'جاري الرفع والنشر...' : 'تأكيد الرفع والنشر الآن'}</span>
        </button>
      </footer>
    </section>
  </AccessibleDialog>;
}
