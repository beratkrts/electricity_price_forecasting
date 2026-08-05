import React from 'react';
import { NavLink } from 'react-router-dom';
import { Download, Home as HomeIcon, TrendingUp, BarChart2, Sun, Moon } from 'lucide-react';

type CurrencyMode = 'TRY' | 'USD';
type ThemeMode = 'dark' | 'light';

interface HeaderProps {
  onRefresh?: () => void;
  onOpenExport: () => void;
  intersectionCount?: number;
  currencyMode?: CurrencyMode;
  onCurrencyChange?: (mode: CurrencyMode) => void;
  themeMode?: ThemeMode;
  onToggleTheme?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onOpenExport,
  currencyMode = 'TRY',
  onCurrencyChange,
  themeMode = 'dark',
  onToggleTheme
}) => {
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
          <img
            src="/etkb-logo.png"
            alt="T.C. Enerji ve Tabii Kaynaklar Bakanlığı"
            style={{
              width: '44px',
              height: '44px',
              objectFit: 'contain',
              filter: 'drop-shadow(0 2px 8px rgba(225, 29, 72, 0.4))'
            }}
          />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '1.2rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#fff', margin: 0 }}>
                ETKB Elektrik Fiyat Tahminleme
              </h1>
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
                color: currencyMode === 'TRY' ? '#ffffffff' : '#94a3b8',
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
                color: currencyMode === 'USD' ? '#ffffffff' : '#94a3b8',
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

          {/* Light / Dark Theme Switcher */}
          <button
            onClick={onToggleTheme}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '8px',
              background: themeMode === 'light' ? 'rgba(241, 245, 249, 0.9)' : 'rgba(15, 23, 42, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: themeMode === 'light' ? '#0f172a' : '#fbbf24',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.8rem',
              transition: 'all 0.2s ease'
            }}
            title={themeMode === 'light' ? 'Koyu Temaya Geç' : 'Açık Temaya Geç'}
          >
            {themeMode === 'light' ? <Moon size={16} color="#0f172a" /> : <Sun size={16} color="#fbbf24" />}
            <span>{themeMode === 'light' ? 'Koyu Mod' : 'Açık Mod'}</span>
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
            İndir
          </button>

        </div>
      </div>
    </header>
  );
};
