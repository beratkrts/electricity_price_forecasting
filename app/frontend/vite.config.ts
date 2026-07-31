import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import https from 'https';
import { execSync } from 'child_process';

const dataDir = path.resolve(__dirname, '../../data');

function energyDataPlugin() {
  return {
    name: 'energy-data-plugin',
    configureServer(server: any) {
      server.middlewares.use((req: any, res: any, next: any) => {
        if (req.url?.startsWith('/api/db-data')) {
          const url = new URL(req.url, `http://${req.headers.host}`);
          const dateParam = url.searchParams.get('date');
          const typeParam = url.searchParams.get('type'); // e.g., 'mcp', 'kgup', 'smp', 'lightgbm' etc.

          if (!dateParam || !typeParam) {
            res.statusCode = 400;
            return res.end(JSON.stringify({ error: 'date and type required' }));
          }

          try {
            const pyPath = path.join(process.cwd(), 'query_db.py');
            // Try active environment python or fallback to system python/python3
            const pythonExe = process.platform === 'win32'
              ? (fs.existsSync(path.resolve(__dirname, '../../.venv/Scripts/python.exe')) 
                  ? path.resolve(__dirname, '../../.venv/Scripts/python.exe') 
                  : 'python')
              : (fs.existsSync(path.resolve(__dirname, '../../.venv/bin/python')) 
                  ? path.resolve(__dirname, '../../.venv/bin/python') 
                  : 'python3');

            const pyOutput = execSync(`"${pythonExe}" "${pyPath}" "${dateParam}" "${typeParam}"`, { encoding: 'utf-8' });
            res.setHeader('Content-Type', 'application/json');
            return res.end(pyOutput);
          } catch (err) {
            res.statusCode = 500;
            return res.end(JSON.stringify({ error: 'Database query failed' }));
          }
        } else if (req.url?.startsWith('/api/fx')) {
          // Fetch live rates from Yahoo Finance
          https.get('https://query1.finance.yahoo.com/v8/finance/chart/USDTRY=X', (yRes) => {
            let data = '';
            yRes.on('data', chunk => data += chunk);
            yRes.on('end', () => {
              try {
                const parsed = JSON.parse(data);
                const result = parsed.chart.result[0];
                const price = result.meta.regularMarketPrice;
                const prevClose = result.meta.previousClose;
                
                https.get('https://query1.finance.yahoo.com/v8/finance/chart/EURTRY=X', (eRes) => {
                  let eData = '';
                  eRes.on('data', chunk => eData += chunk);
                  eRes.on('end', () => {
                    try {
                      const eParsed = JSON.parse(eData);
                      const eResult = eParsed.chart.result[0];
                      const ePrice = eResult.meta.regularMarketPrice;
                      const ePrevClose = eResult.meta.previousClose;
                      
                      res.setHeader('Content-Type', 'application/json');
                      res.end(JSON.stringify({
                        USD: { price, prevClose },
                        EUR: { price: ePrice, prevClose: ePrevClose }
                      }));
                    } catch (e) {
                      res.statusCode = 500;
                      res.end(JSON.stringify({ error: 'Failed to parse EUR' }));
                    }
                  });
                }).on('error', () => {
                  res.statusCode = 500;
                  res.end(JSON.stringify({ error: 'Network error EUR' }));
                });
              } catch (e) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: 'Failed to parse USD' }));
              }
            });
          }).on('error', () => {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: 'Network error USD' }));
          });
          return;
        }
        next();
      });
    }
  };
}

export default defineConfig({
  plugins: [react(), energyDataPlugin()],
  server: {
    port: 3000,
    host: true
  }
});
