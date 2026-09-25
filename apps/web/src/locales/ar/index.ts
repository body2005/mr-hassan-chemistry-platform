import { commonAr } from "./common";
import { authAr } from "./auth";
import { coursesAr } from "./courses";
import { teacherAr } from "./teacher";
import { paymentsAr } from "./payments";

export const ar = {
  common: commonAr,
  auth: authAr,
  courses: coursesAr,
  teacher: teacherAr,
  payments: paymentsAr,
};

export type LocaleSchema = typeof ar;
