import { apiRequest } from './apiClient';
import type { CustomColumn } from '../types/lms';

export type TrackingValue = string | number | boolean;
export type TrackingValues = Record<string, Record<string, TrackingValue>>;
interface ApiColumn {
  id: string; name: string; data_type: CustomColumn['dataType'];
  table_context: CustomColumn['tableContext']; academic_year: CustomColumn['academicYear']; created_at: string;
}
function mapColumn(column: ApiColumn): CustomColumn {
  return { id: column.id, name: column.name, dataType: column.data_type,
    tableContext: column.table_context, academicYear: column.academic_year, createdAt: column.created_at };
}
const base = '/teacher-tracking';
export const studentTrackingService = {
  async getSnapshot(): Promise<{ columns: CustomColumn[]; values: TrackingValues }> {
    const snapshot = await apiRequest<{ columns: ApiColumn[]; values: TrackingValues }>(base, { skipCache: true });
    return { columns: snapshot.columns.map(mapColumn), values: snapshot.values };
  },
  async addColumn(column: CustomColumn): Promise<CustomColumn> {
    return mapColumn(await apiRequest<ApiColumn>(`${base}/columns`, { method: 'POST', body: JSON.stringify({
      name: column.name, data_type: column.dataType, table_context: column.tableContext, academic_year: column.academicYear,
    }) }));
  },
  async deleteColumn(id: string): Promise<void> {
    await apiRequest(`${base}/columns/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },
  async saveValue(studentId: string, columnId: string, value: TrackingValue): Promise<TrackingValue> {
    const saved = await apiRequest<{ value: TrackingValue }>(
      `${base}/columns/${encodeURIComponent(columnId)}/students/${encodeURIComponent(studentId)}`,
      { method: 'PUT', body: JSON.stringify({ value }) });
    return saved.value;
  },
};
