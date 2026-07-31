import { CurrencyRate } from '../types/currency';

export const INITIAL_CURRENCY_RATES: CurrencyRate[] = [
  {
    symbol: 'USD/TRY',
    name: 'ABD Doları',
    price: 33.15, // Approx current base price
    change: 0.00,
    unit: '₺',
    category: 'fx',
    updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  },
  {
    symbol: 'EUR/TRY',
    name: 'Euro',
    price: 36.10, // Approx current base price
    change: 0.00,
    unit: '₺',
    category: 'fx',
    updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  },
  {
    symbol: 'BRENT',
    name: 'Brent Petrol',
    price: 78.45,
    change: 1.15,
    unit: '$/bbl',
    category: 'commodity',
    updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  },
  {
    symbol: 'TTF GAS',
    name: 'TTF Doğalgaz',
    price: 36.80,
    change: -0.65,
    unit: '€/MWh',
    category: 'commodity',
    updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  },
  {
    symbol: 'EU ETS',
    name: 'Karbon İzni',
    price: 68.90,
    change: 0.82,
    unit: '€/t',
    category: 'carbon',
    updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  },
  {
    symbol: 'PTF AVG',
    name: 'Günlük PTF Ort.',
    price: 2640.50,
    change: 2.10,
    unit: '₺/MWh',
    category: 'commodity',
    updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
];

// Base prices to calculate percentage change
const basePrices: Record<string, number> = {};
INITIAL_CURRENCY_RATES.forEach(r => { basePrices[r.symbol] = r.price; });

let lastRates = [...INITIAL_CURRENCY_RATES];

export async function fetchMarketData(): Promise<CurrencyRate[]> {
  try {
    const res = await fetch('/api/fx');
    const data = await res.json();
    
    if (data && data.USD && data.EUR) {
      const usdTry = data.USD.price;
      const eurTry = data.EUR.price;
      
      lastRates = lastRates.map(rate => {
        let newPrice = rate.price;
        let basePrice = basePrices[rate.symbol] || rate.price;
        let newChange = rate.change;
        
        if (rate.symbol === 'USD/TRY') {
          newPrice = usdTry;
          basePrice = data.USD.prevClose || basePrice;
          newChange = ((newPrice - basePrice) / basePrice) * 100;
        } else if (rate.symbol === 'EUR/TRY') {
          newPrice = eurTry;
          basePrice = data.EUR.prevClose || basePrice;
          newChange = ((newPrice - basePrice) / basePrice) * 100;
        }
        
        return {
          ...rate,
          price: Number(newPrice.toFixed(4)),
          change: Number(newChange.toFixed(2)),
          updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        };
      });
    }
  } catch (error) {
    console.error("FX fetch failed", error);
  }
  return lastRates;
}

export function simulateMarketTick(rates: CurrencyRate[]): CurrencyRate[] {
  return rates.map((rate) => {
    // Random micro-oscillation (0.005%)
    const deltaPercent = (Math.random() - 0.49) * 0.005;
    const newPrice = +(rate.price * (1 + deltaPercent / 100)).toFixed(4);
    
    const basePrice = basePrices[rate.symbol] || rate.price;
    const newChange = ((newPrice - basePrice) / basePrice) * 100;

    return {
      ...rate,
      price: newPrice,
      change: Number(newChange.toFixed(2)),
      updatedAt: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    };
  });
}
