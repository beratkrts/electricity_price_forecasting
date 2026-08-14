import { CurrencyRate } from '../types/currency';

interface TickerDef {
  symbol: string;
  name: string;
  unit: string;
  category: CurrencyRate['category'];
  /** Key this quote arrives under in the /api/fx response. */
  apiKey: string;
  decimals: number;
}

/**
 * Every ticker here is backed by a real quote from /api/fx.
 *
 * EU ETS carbon is intentionally absent: no free provider exposes a usable EUA
 * price, so there is nothing honest to show for it.
 */
const TICKER_DEFS: TickerDef[] = [
  { symbol: 'USD/TRY', name: 'ABD Doları', unit: '₺', category: 'fx', apiKey: 'USD', decimals: 4 },
  { symbol: 'EUR/TRY', name: 'Euro', unit: '₺', category: 'fx', apiKey: 'EUR', decimals: 4 },
  { symbol: 'BRENT', name: 'Brent Petrol', unit: '$/bbl', category: 'commodity', apiKey: 'BRENT', decimals: 2 },
  { symbol: 'TTF GAS', name: 'TTF Doğalgaz', unit: '€/MWh', category: 'commodity', apiKey: 'TTF', decimals: 2 },
  { symbol: 'PTF ORT.', name: 'Günlük PTF Ort.', unit: '₺/MWh', category: 'commodity', apiKey: 'PTF_AVG', decimals: 2 },
];

/**
 * The ticker starts empty and only ever shows quotes that /api/fx actually returned.
 * It used to be seeded with hardcoded prices (Brent $78.45, TTF €36.80, EU ETS €68.90,
 * PTF ₺2640.50) that no code path ever refreshed, so the bar displayed invented numbers
 * indefinitely while looking live.
 */
export const INITIAL_CURRENCY_RATES: CurrencyRate[] = [];

interface Quote {
  price: number;
  prevClose?: number;
}

let lastRates: CurrencyRate[] = [];

function nowLabel(): string {
  return new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export async function fetchMarketData(): Promise<CurrencyRate[]> {
  try {
    const res = await fetch('/api/fx');
    if (!res.ok) throw new Error(`/api/fx returned ${res.status}`);
    const data: Record<string, Quote> = await res.json();
    const updatedAt = nowLabel();

    const rates = TICKER_DEFS.flatMap<CurrencyRate>((def) => {
      const quote = data?.[def.apiKey];
      if (!quote || typeof quote.price !== 'number' || !Number.isFinite(quote.price)) {
        // Quote unavailable this cycle — omit the ticker rather than invent a price.
        return [];
      }
      const base =
        typeof quote.prevClose === 'number' && Number.isFinite(quote.prevClose) && quote.prevClose !== 0
          ? quote.prevClose
          : quote.price;
      return [{
        symbol: def.symbol,
        name: def.name,
        price: Number(quote.price.toFixed(def.decimals)),
        change: Number((((quote.price - base) / base) * 100).toFixed(2)),
        unit: def.unit,
        category: def.category,
        updatedAt,
      }];
    });

    if (rates.length > 0) {
      lastRates = rates;
    }
  } catch (error) {
    // Keep the previous real values on a transient failure instead of blanking the bar.
    console.error('FX fetch failed', error);
  }
  return lastRates;
}
