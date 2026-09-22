import { commonAr } from "./common";
import { authAr } from "./auth";
import { coursesAr } from "./courses";
import { teacherAr } from "./teacher";
import { paymentsAr } from "./payments";
import { aiAr } from "./ai";

export const ar = {
  common: commonAr,
  auth: authAr,
  courses: coursesAr,
  teacher: teacherAr,
  payments: paymentsAr,
  ai: aiAr,
};

export type LocaleSchema = typeof ar;
