import React from 'react';
import { HistoricalBenchmark } from '../components/dashboard/HistoricalBenchmark';

interface AnalysisProps {
  currencyMode?: 'TRY' | 'USD';
  usdRate?: number;
}

export const Analysis: React.FC<AnalysisProps> = ({ currencyMode = 'USD', usdRate = 33.15 }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <HistoricalBenchmark currencyMode={currencyMode} usdRate={usdRate} />
    </div>
  );
};
