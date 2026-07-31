export interface CurrencyRate {
  symbol: string; // e.g. "USD/TRY", "EUR/TRY", "BRENT", "TTF", "EU ETS"
  name: string;
  price: number;
  change: number; // percentage change e.g. +0.45 or -0.12
  unit: string; // "₺", "€", "$", "$/bbl", "€/MWh", "€/t"
  category: 'fx' | 'commodity' | 'carbon';
  updatedAt: string;
}

export interface MarketTickerState {
  rates: CurrencyRate[];
  lastRefresh: string;
  isLive: boolean;
}
