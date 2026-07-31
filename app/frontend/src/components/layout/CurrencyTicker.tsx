import React from 'react';
import { TrendingUp, TrendingDown, Clock, Globe } from 'lucide-react';
import { CurrencyRate } from '../../types/currency';

interface CurrencyTickerProps {
  rates: CurrencyRate[];
  lastRefresh: string;
}

export const CurrencyTicker: React.FC<CurrencyTickerProps> = ({ rates, lastRefresh }) => {
  // Duplicate array to achieve smooth seamless infinite loop marquee scrolling
  const displayRates = [...rates, ...rates, ...rates];

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      height: '42px',
      background: 'rgba(7, 10, 18, 0.95)',
      backdropFilter: 'blur(12px)',
      borderTop: '1px solid rgba(255, 255, 255, 0.1)',
      display: 'flex',
      alignItems: 'center',
      zIndex: 100,
      overflow: 'hidden'
    }}>
      {/* Ticker Header Tag */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
        padding: '0 16px',
        height: '100%',
        borderRight: '1px solid rgba(255, 255, 255, 0.1)',
        fontSize: '0.78rem',
        fontWeight: 700,
        color: '#38bdf8',
        whiteSpace: 'nowrap',
        zIndex: 2
      }}>
        <Globe size={14} />
        <span>CANLI PİYASA & KUR</span>
        <span className="live-dot" style={{ marginLeft: '4px' }} />
      </div>

      {/* Marquee Track */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        <div className="ticker-track">
          {displayRates.map((rate, idx) => {
            const isPositive = rate.change >= 0;
            return (
              <div
                key={`${rate.symbol}-${idx}`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '0 24px',
                  fontSize: '0.8rem',
                  borderRight: '1px dashed rgba(255, 255, 255, 0.08)',
                  whiteSpace: 'nowrap'
                }}
              >
                <span style={{ color: '#94a3b8', fontWeight: 600 }}>{rate.symbol}</span>
                <span style={{ color: '#fff', fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
                  {rate.price} {rate.unit}
                </span>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '2px',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  color: isPositive ? '#10b981' : '#f43f5e',
                  background: isPositive ? 'rgba(16, 185, 129, 0.12)' : 'rgba(244, 63, 94, 0.12)',
                  padding: '2px 6px',
                  borderRadius: '4px'
                }}>
                  {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  {isPositive ? '+' : ''}{rate.change}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Live Timestamp right badge */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '0 16px',
        height: '100%',
        background: 'rgba(15, 23, 42, 0.9)',
        borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
        fontSize: '0.72rem',
        color: '#64748b',
        whiteSpace: 'nowrap',
        zIndex: 2
      }}>
        <Clock size={12} />
        <span>Son Güncelleme: {lastRefresh}</span>
      </div>
    </div>
  );
};
