export function formatCurrency(value: number, currency: string = '₺', decimals: number = 2): string {
  if (isNaN(value) || value === null) return '-';
  const formatted = new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(value);
  return `${formatted} ${currency}`;
}

export function formatPercent(value: number, includeSign: boolean = false): string {
  if (isNaN(value) || value === null) return '0.00%';
  const prefix = includeSign && value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

export function formatNumber(value: number, decimals: number = 2): string {
  if (isNaN(value) || value === null) return '-';
  return new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(value);
}

export function formatDateString(dateStr: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric'
  }).format(date);
}

export function formatToDDMMYYYY(dateStr: string): string {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length >= 3) {
    const day = parts[2].substring(0, 2);
    return `${day}.${parts[1]}.${parts[0]}`;
  }
  return dateStr;
}

export function formatTimestampToDDMMYYYY(ts: string): string {
  if (!ts) return '';
  const parts = ts.split(' ');
  if (parts.length > 0) {
    const datePart = formatToDDMMYYYY(parts[0]);
    return parts.length > 1 ? `${datePart} ${parts[1]}` : datePart;
  }
  return ts;
}