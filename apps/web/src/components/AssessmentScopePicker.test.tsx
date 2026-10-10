import { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AssessmentScopePicker } from './AssessmentScopePicker';
import type { Course } from '../types/lms';

const courses = [{id:'course', title:'الصف الأول', lessons:[
  {id:'one', moduleId:'u1', unitTitle:'الوحدة الأولى', title:'الدرس الأول'},
  {id:'two', moduleId:'u2', unitTitle:'الوحدة الثانية', title:'الدرس الثاني'},
]}] as Course[];
let host: HTMLDivElement, root: ReturnType<typeof createRoot>;
function Harness() {
  const [lessons, setLessons] = useState<string[]>([]), [modules, setModules] = useState<string[]>([]);
  return <><AssessmentScopePicker courses={courses} courseId="course" lessonIds={lessons} moduleIds={modules}
    onChange={(_, nextLessons, nextModules) => {setLessons(nextLessons); setModules(nextModules);}} />
    <output>{JSON.stringify({lessons, modules})}</output></>;
}
beforeEach(() => {vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host=document.createElement('div'); document.body.append(host); root=createRoot(host);});
afterEach(async () => {await act(async()=>root.unmount()); host.remove(); vi.unstubAllGlobals();});
it('keeps multiple lessons and whole units selected together', async () => {
  await act(async()=>root.render(<Harness/>));
  const choose = async (text: string) => {const label = [...host.querySelectorAll('label')].find(label=>label.textContent?.includes(text))!;
    await act(async()=>label.querySelector('input')!.click());};
  await choose('الدرس الأول'); await choose('الدرس الثاني'); await choose('الوحدة الأولى'); await choose('الوحدة الثانية');
  expect(JSON.parse(host.querySelector('output')!.textContent!)).toEqual({lessons:['one','two'],modules:['u1','u2']});
  await choose('الدرس الأول');
  expect(JSON.parse(host.querySelector('output')!.textContent!).lessons).toEqual(['two']);
});
