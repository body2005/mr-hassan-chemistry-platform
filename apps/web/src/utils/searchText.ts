/** Fold spelling variants only for matching; never change displayed or saved text. */
export function searchText(value: string | null | undefined): string {
  return (value || '').normalize('NFKC').replace(/[أإآٱ]/g, 'ا').replace(/[\u064b-\u065f\u0670\u0640]/g, '').toLocaleLowerCase().trim();
}
