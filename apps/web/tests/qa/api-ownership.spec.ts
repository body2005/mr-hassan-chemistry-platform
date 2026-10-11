import type { APIRequest, APIRequestContext } from "@playwright/test";
import { expect, test } from "./qaTest";
import { cookieApi } from './cookieApi';

const baseURL = `${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/`;

async function asUser(request: APIRequest, email: string, password: string) {
  return cookieApi(request, email, password);
}

async function created(context: APIRequestContext, path: string, data: unknown) {
  const response = await context.post(path, { data });
  expect(response.status(), `${path}: ${await response.text()}`).toBe(201);
  return response.json();
}

test("manual quiz and assignment lifecycle enforces student and teacher ownership", async ({ playwright, page }) => {
  const teacher = await asUser(playwright.request, "teacher@demo.com", "qa-teacher-pass");
  const otherTeacher = await asUser(playwright.request, "teacher2@example.com", "qa-teacher2-pass");
  const student = await asUser(playwright.request, "student01@demo.com", "qa-student-pass");
  const otherStudent = await asUser(playwright.request, "student02@demo.com", "qa-student-pass");
  const anonymous = await playwright.request.newContext({ ignoreHTTPSErrors: false, baseURL });
  try {
    const code = `QA${Date.now()}`;
    const course = await created(teacher.context, "courses", { code, title: "QA Chemistry" });
    const module = await created(teacher.context, `courses/${course.id}/modules`, { title: "QA Unit", position: 1 });
    const lesson = await created(teacher.context, `modules/${module.id}/lessons`, {
      title: "QA Lesson", kind: "article", position: 1, content: "QA-only content", price_egp: 0,
    });
    expect(lesson.id).toBeTruthy();
    const fakeVideo = await teacher.context.post(`lessons/${lesson.id}/video`, {
      multipart: { file: { name: "fake.mp4", mimeType: "video/mp4", buffer: Buffer.from("not an MP4") } },
    });
    expect(fakeVideo.status()).toBe(422);
    const fakePdf = await teacher.context.post(`lessons/${lesson.id}/materials`, {
      multipart: { file: { name: "fake.pdf", mimeType: "application/pdf", buffer: Buffer.from("not a PDF") } },
    });
    expect(fakePdf.status()).toBe(422);
    const paidLesson = await created(teacher.context, `modules/${module.id}/lessons`, {
      title: "QA Paid Lesson", kind: "article", position: 2, content: "Private content", price_egp: 50,
    });
    const paidMaterialResponse = await teacher.context.post(`lessons/${paidLesson.id}/materials`, {
      multipart: { file: { name: "qa-notes.txt", mimeType: "text/plain", buffer: Buffer.from("QA only") } },
    });
    expect(paidMaterialResponse.status()).toBe(201);
    const paidMaterial = await paidMaterialResponse.json();
    expect((await teacher.context.post(`courses/${course.id}/publish`)).status()).toBe(200);
    expect((await student.context.post(`courses/${course.id}/enroll`)).status()).toBe(200);
    expect((await otherStudent.context.post(`courses/${course.id}/enroll`)).status()).toBe(200);
    expect((await teacher.context.get(`lessons/${paidLesson.id}/materials/${paidMaterial.id}/download`)).status()).toBe(200);
    expect((await student.context.get(`lessons/${paidLesson.id}/materials/${paidMaterial.id}/download`)).status()).toBe(403);
    expect((await anonymous.get(`lessons/${paidLesson.id}/materials/${paidMaterial.id}/download`)).status()).toBe(401);

    const question = await created(teacher.context, "questions", {
      course_id: course.id, question_type: "multiple_choice", prompt: "What is H2O?",
      options: ["Water", "Salt"], correct_answer: "Water", points: 5,
    });
    const otherCourse = await created(otherTeacher.context, "courses", {
      code: `${code}B`, title: "QA Other Teacher Course",
    });
    const copiedQuestion = await otherTeacher.context.post("quizzes", {
      data: { course_id: otherCourse.id, title: "Unauthorized Question", question_ids: [question.id] },
    });
    expect(copiedQuestion.status()).toBe(403);
    const quiz = await created(teacher.context, "quizzes", {
      course_id: course.id, title: "QA Quiz", question_ids: [question.id], duration_seconds: 120,
    });
    expect((await teacher.context.post(`quizzes/${quiz.id}/publish`)).status()).toBe(200);
    const assignment = await created(teacher.context, "assignments", {
      course_id: course.id, title: "QA Homework", prompt: "Explain H2O", max_score: 100,
    });
    expect((await teacher.context.post(`assignments/${assignment.id}/publish`)).status()).toBe(200);

    expect((await anonymous.post(`quizzes/${quiz.id}/attempts`)).status()).toBe(401);
    expect((await student.context.post("courses", { data: { code: "NO", title: "Denied" } })).status()).toBe(403);
    expect((await otherTeacher.context.post(`quizzes/${quiz.id}/publish`)).status()).toBe(403);
    const attempt = await student.context.post(`quizzes/${quiz.id}/attempts`);
    expect(attempt.status()).toBe(200);
    const attemptId = (await attempt.json()).id as string;
    expect((await otherStudent.context.post(`quiz-attempts/${attemptId}/submit`, {
      data: { submission_key: "qa-other-student", answers: [] },
    })).status()).toBe(404);
    const answer = { submission_key: `qa-quiz-${code}`, answers: [{ question_id: question.id, answer: "Water" }] };
    const submitted = await student.context.post(`quiz-attempts/${attemptId}/submit`, { data: answer });
    expect(submitted.status()).toBe(200);
    expect((await submitted.json()).score).toBeNull();
    const duplicate = await student.context.post(`quiz-attempts/${attemptId}/submit`, { data: answer });
    expect(duplicate.status()).toBe(200);
    expect((await duplicate.json()).id).toBe(attemptId);
    expect((await duplicate.json()).score).toBeNull();
    const pending = await student.context.get(`quizzes/${quiz.id}/result?attempt_id=${attemptId}`);
    expect((await pending.json()).summary).toBeNull();
    expect((await otherTeacher.context.post(`quiz-attempts/${attemptId}/approve`)).status()).toBe(404);
    expect((await teacher.context.post(`quiz-attempts/${attemptId}/approve`)).status()).toBe(200);
    const released = await student.context.get(`quizzes/${quiz.id}/result?attempt_id=${attemptId}`);
    expect((await released.json()).score).toBe(5);
    const secondAttempt = await otherStudent.context.post(`quizzes/${quiz.id}/attempts`);
    expect(secondAttempt.status()).toBe(200);
    const secondAttemptId = (await secondAttempt.json()).id as string;
    const concurrentAnswer = {
      submission_key: `qa-concurrent-${code}`,
      answers: [{ question_id: question.id, answer: "Water" }],
    };
    const concurrent = await Promise.all(Array.from({ length: 8 }, () =>
      otherStudent.context.post(`quiz-attempts/${secondAttemptId}/submit`, { data: concurrentAnswer })));
    expect(concurrent.map((response) => response.status())).toEqual(Array(8).fill(200));

    const homework = await student.context.post(`assignments/${assignment.id}/submissions`, {
      data: { answer_text: "Water is H2O", idempotency_key: `qa-homework-${code}` },
    });
    expect(homework.status()).toBe(200);
    const submissionId = (await homework.json()).id as string;
    const own = await student.context.get("submissions/me");
    expect((await own.json()).some((item: { id: string }) => item.id === submissionId)).toBe(true);
    const otherOwn = await otherStudent.context.get("submissions/me");
    expect((await otherOwn.json()).some((item: { id: string }) => item.id === submissionId)).toBe(false);
    expect((await otherStudent.context.get(`submissions/${submissionId}/file`)).status()).toBe(403);
    expect((await otherTeacher.context.post(`submissions/${submissionId}/grade`, {
      data: { final_score: 80, approve: true },
    })).status()).toBe(403);
    await page.goto("/#auth");
    const teacherSignIn = page.locator("form").first();
    await teacherSignIn.locator('input[type="text"]').fill("teacher@demo.com");
    await teacherSignIn.locator('input[type="password"]').fill("qa-teacher-pass");
    await teacherSignIn.locator('button[type="submit"]').click();
    await expect(page.locator(".profile-button")).toHaveCount(1);
    await page.goto("/#submissions");
    await page.getByPlaceholder("بحث باسم الطالب، رقم ولي الأمر، أو البريد الإلكتروني...").fill("student01@demo.com");
    await page.getByRole("button", { name: "معاينة وتعديل درجة", exact: true }).click();
    await page.getByLabel("درجة الواجب").fill("80");
    await page.getByRole("button", { name: "اعتماد وحفظ الدرجة" }).click();
    await expect.poll(async () => {
      const listed = await teacher.context.get("submissions");
      const items = await listed.json() as Array<{ id: string; final_score: number }>;
      return items.find((item) => item.id === submissionId)?.final_score;
    }).toBe(80);

    const otherTeacherSubmissions = await otherTeacher.context.get("submissions");
    expect((await otherTeacherSubmissions.json()).some((item: { id: string }) => item.id === submissionId)).toBe(false);
    const otherTeacherUsers = await otherTeacher.context.get("users");
    expect((await otherTeacherUsers.json()).some((item: { id: string }) => item.id === student.id)).toBe(false);
    const otherTeacherQuestions = await otherTeacher.context.get("questions");
    expect((await otherTeacherQuestions.json()).some((item: { id: string }) => item.id === question.id)).toBe(false);
    const otherTeacherQuizzes = await otherTeacher.context.get("quizzes");
    expect((await otherTeacherQuizzes.json()).some((item: { id: string }) => item.id === quiz.id)).toBe(false);
    const otherTeacherAssignments = await otherTeacher.context.get("assignments");
    expect((await otherTeacherAssignments.json()).some((item: { id: string }) => item.id === assignment.id)).toBe(false);
    const otherTeacherNotifications = await otherTeacher.context.get("notifications");
    expect((await otherTeacherNotifications.json()).some((item: { message: string }) => item.message.includes("QA Homework"))).toBe(false);
  } finally {
    await Promise.all([
      teacher.context.dispose(), otherTeacher.context.dispose(),
      student.context.dispose(), otherStudent.context.dispose(), anonymous.dispose(),
    ]);
  }
});
