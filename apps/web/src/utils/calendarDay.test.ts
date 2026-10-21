import { expect, it } from 'vitest';
import { calendarTimeConflicts } from './calendarDay';
import type { CalendarScheduleEvent } from '../types/lms';

it('matches the Cairo minute across formats and scopes, excluding self and cancelled entries', () => {
  const target: CalendarScheduleEvent = {id:'draft', creatorId:'teacher', academicYear:'1st_secondary',
    date:'2035-05-13', time:'٠١:٣٠ ص', contentType:'lesson', dayName:'درس'};
  const sibling = {...target, id:'saved', startsAt:'2035-05-12T22:30:00Z'};
  expect(calendarTimeConflicts([
    sibling, target, {...sibling,id:'cancelled',isCancelled:true},
    {...sibling,id:'other-teacher',creatorId:'another'},
    {...sibling,id:'other-grade',academicYear:'2nd_secondary'},
    {...sibling,id:'other-minute',startsAt:'2035-05-12T22:31:00Z'},
    {...sibling,id:'other-day',startsAt:'2035-05-13T22:30:00Z'},
    {...sibling,id:'global',academicYear:'all'},
  ], target, 'teacher').map(event => event.id)).toEqual(['saved','global']);
});
