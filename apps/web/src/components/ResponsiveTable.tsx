import { useLayoutEffect, useRef, type ComponentProps } from 'react';

/** Keep native table semantics on desktop and label each cell in mobile cards. */
export function ResponsiveTable({ children, className = '', ...props }: ComponentProps<'table'>) {
  const ref = useRef<HTMLTableElement>(null);
  useLayoutEffect(() => {
    const table = ref.current;
    if (!table) return;
    const headings = Array.from(table.tHead?.rows[0]?.cells ?? []).map(cell => cell.textContent ?? '');
    for (const body of table.tBodies) for (const row of body.rows) {
      for (let index = 0; index < row.cells.length; index++) {
        const cell = row.cells[index];
        if (cell.colSpan === 1) cell.dataset.label = headings[index] ?? '';
      }
    }
  }, [children]);
  return <table {...props} ref={ref} className={`${className} mobile-card-table`}>{children}</table>;
}
