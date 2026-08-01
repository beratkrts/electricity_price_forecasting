import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Activity, Download, RefreshCw, Zap, Info, Home as HomeIcon, TrendingUp, BarChart2 } from 'lucide-react';

interface HeaderProps {
  onRefresh: () => void;
  onOpenExport: () => void;
  intersectionCount: number;
  currencyMode?: 'TRY' | 'USD';
  onCurrencyChange?: (mode: 'TRY' | 'USD') => void;
}

export const Header: React.FC<HeaderProps> = ({
  onRefresh,
  onOpenExport,
  intersectionCount,
  currencyMode = 'TRY',
  onCurrencyChange
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const location = useLocation();

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '8px 16px',
    borderRadius: '8px',
    textDecoration: 'none',
    fontSize: '0.85rem',
    fontWeight: 600,
    transition: 'all 0.2s ease',
    background: isActive ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
    color: isActive ? '#38bdf8' : '#94a3b8',
    border: `1px solid ${isActive ? 'rgba(56, 189, 248, 0.3)' : 'transparent'}`
  });

  return (
    <header className="glass-panel" style={{ margin: '16px 20px 0 20px', padding: '12px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        
        {/* Logo & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #38bdf8 0%, #10b981 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px rgba(56, 189, 248, 0.35)'
          }}>
            <Zap size={22} color="#070a12" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '1.2rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#fff', margin: 0 }}>
                EPİAŞ PTF Tahminleme
              </h1>
              {location.pathname === '/forecast' && (
                <span className="ping-badge" style={{ animation: intersectionCount > 0 ? 'ping-glow 2s infinite' : 'none' }}>
                  <Activity size={12} />
                  {intersectionCount} Kesişim
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
              <span style={{ fontSize: '0.68rem', color: '#fbbf24', background: 'rgba(251, 191, 36, 0.12)', padding: '1px 6px', borderRadius: '4px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <Info size={10} /> Demo Modu Aktif
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.6)', padding: '4px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
          <NavLink to="/" style={navLinkStyle} end>
            <HomeIcon size={16} />
            Ana Sayfa
          </NavLink>
          <NavLink to="/forecast" style={navLinkStyle}>
            <TrendingUp size={16} />
            Tahmin Kıyaslama
          </NavLink>
          <NavLink to="/analysis" style={navLinkStyle}>
            <BarChart2 size={16} />
            Analizler
          </NavLink>
        </nav>

        {/* Right Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          
          {/* TRY / USD Currency Mode Switcher */}
          <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.8)', padding: '3px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <button
              onClick={() => onCurrencyChange && onCurrencyChange('TRY')}
              style={{
                background: currencyMode === 'TRY' ? 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)' : 'transparent',
                color: currencyMode === 'TRY' ? '#0f172a' : '#94a3b8',
                border: 'none',
                padding: '5px 12px',
                borderRadius: '6px',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span>₺</span> TRY
            </button>
            <button
              onClick={() => onCurrencyChange && onCurrencyChange('USD')}
              style={{
                background: currencyMode === 'USD' ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : 'transparent',
                color: currencyMode === 'USD' ? '#0f172a' : '#94a3b8',
                border: 'none',
                padding: '5px 12px',
                borderRadius: '6px',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span>$</span> USD
            </button>
          </div>

          {/* Refresh button */}
          <button
            onClick={handleRefreshClick}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '8px 14px',
              borderRadius: '8px',
              background: isRefreshing ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: isRefreshing ? '#38bdf8' : '#f8fafc',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
            {isRefreshing ? 'Yenileniyor...' : 'Verileri Yenile'}
          </button>

          {/* Download Export button */}
          <button
            onClick={onOpenExport}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              border: 'none',
              color: '#ffffff',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)'
            }}
          >
            <Download size={15} />
            Rapor İndir
          </button>

        </div>
      </div>
    </header>
  );
};
