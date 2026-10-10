import { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AssessmentScopePicker } from './AssessmentScopePicker';
import type { Course } from '../types/lms';

const courses = [{id:'course', title:'الصف الأول', lessons:[
  {id:'one', moduleId:'u1', unitTitle:'الوحدة الأولى', title:'الدرس الأول'},
  {id:'two', moduleId:'u2', unitTitle:'الوحدة الثانية', title:'الدرس الثاني'},
  {id:'three', moduleId:'u1', unitTitle:'الوحدة الأولى', title:'الدرس الثالث'},
]}] as Course[];
let host: HTMLDivElement, root: ReturnType<typeof createRoot>;
function Harness({ initialLessons = [], initialModules = [], items = courses }: {
  initialLessons?: string[]; initialModules?: string[]; items?: Course[];
}) {
  const [lessons, setLessons] = useState(initialLessons), [modules, setModules] = useState(initialModules);
  const [courseId, setCourseId] = useState('course');
  return <><AssessmentScopePicker courses={items} courseId={courseId} lessonIds={lessons} moduleIds={modules}
    onChange={(id, nextLessons, nextModules) => {setCourseId(id); setLessons(nextLessons); setModules(nextModules);}} />
    <output>{JSON.stringify({lessons, modules})}</output></>;
}
const field = (index: number) => host.querySelectorAll('.assessment-scope-field')[index];
const result = () => JSON.parse(host.querySelector('output')!.textContent!);
const choose = async (index: number, text: string) => {
  const label = [...field(index).querySelectorAll('label')].find(label => label.textContent?.includes(text))!;
  await act(async () => label.querySelector('input')!.click());
};
beforeEach(() => {vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host=document.createElement('div'); document.body.append(host); root=createRoot(host);});
afterEach(async () => {await act(async()=>root.unmount()); host.remove(); vi.unstubAllGlobals();});
it('keeps multiple lessons and whole units selected together', async () => {
  await act(async()=>root.render(<Harness/>));
  expect(host.querySelectorAll('summary')).toHaveLength(2);
  await act(async () => field(0).querySelector('summary')!.click());
  await choose(0, 'الوحدة الأولى'); await choose(0, 'الوحدة الثانية');
  expect(field(0).querySelector('details')!.open).toBe(true);
  await act(async () => field(1).querySelector('summary')!.click());
  await choose(1, 'الدرس الأول'); await choose(1, 'الدرس الثاني');
  expect(result()).toEqual({lessons:['one','two'],modules:['u1','u2']});
  expect(field(0).querySelectorAll('li')).toHaveLength(2);
  expect(field(1).querySelectorAll('li')).toHaveLength(2);
  await choose(1, 'الدرس الأول');
  expect(result()).toEqual({lessons:['two'],modules:['u1','u2']});
});

it('restores selected items and removes one chip without losing other choices', async () => {
  await act(async () => root.render(<Harness initialLessons={['one', 'two']} initialModules={['u1', 'u2']} />));
  expect([...host.querySelectorAll('summary')].map(item => item.textContent)).toEqual(['تم اختيار 2', 'تم اختيار 2']);
  const remove = field(0).querySelector<HTMLButtonElement>('button[aria-label="إلغاء اختيار الوحدة الأولى"]')!;
  await act(async () => remove.click());
  expect(result()).toEqual({lessons:['one','two'], modules:['u2']});
  expect(field(0).querySelector<HTMLInputElement>('input')!.checked).toBe(false);
});

it('lists each unit only once and keeps lessons in a separate field', async () => {
  await act(async () => root.render(<Harness />));
  expect(field(0).querySelectorAll('input')).toHaveLength(2);
  expect(field(1).querySelectorAll('input')).toHaveLength(3);
  await choose(0, 'الوحدة الأولى');
  expect(result()).toEqual({lessons:[], modules:['u1']});
});

it('keeps the course boundary until every current choice is removed', async () => {
  const other = {id:'other', title:'مجموعة أخرى', lessons:[{id:'four', moduleId:'u3', unitTitle:'الوحدة الأخرى', title:'الدرس الآخر'}]} as Course;
  await act(async () => root.render(<Harness items={[...courses, other]} />));
  await choose(0, 'الوحدة الأولى');
  await choose(1, 'الدرس الآخر');
  expect(result()).toEqual({lessons:[], modules:['u1']});
  expect([...field(1).querySelectorAll('input')].at(-1)!.disabled).toBe(true);
  await choose(0, 'الوحدة الأولى');
  await choose(1, 'الدرس الآخر');
  await choose(0, 'الوحدة الأخرى');
  expect(result()).toEqual({lessons:['four'], modules:['u3']});
});

it('closes on outside clicks and Escape without clearing selected items', async () => {
  await act(async () => root.render(<Harness initialLessons={['one']} />));
  const details = field(1).querySelector('details')!;
  const summary = details.querySelector('summary')!;
  await act(async () => summary.click());
  await act(async () => document.body.dispatchEvent(new Event('pointerdown', {bubbles:true})));
  expect(details.open).toBe(false);
  await act(async () => summary.click());
  await act(async () => summary.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})));
  expect(details.open).toBe(false);
  expect(document.activeElement).toBe(summary);
  expect(result()).toEqual({lessons:['one'], modules:[]});
});

it('explains when no content is available in either dropdown', async () => {
  await act(async () => root.render(<Harness items={[]} />));
  expect(host.querySelectorAll('summary')).toHaveLength(2);
  expect(host.querySelectorAll('input')).toHaveLength(0);
  expect(field(0).textContent).toContain('لا توجد وحدات');
  expect(field(1).textContent).toContain('أضف درسًا');
});
