export default function HelpPage() {
  const sectionStyle: React.CSSProperties = { marginBottom: '2rem' };
  const h2Style: React.CSSProperties = { borderBottom: '2px solid #e0e4ef', paddingBottom: 6, marginBottom: 12 };
  const codeStyle: React.CSSProperties = {
    background: '#f5f7fb', padding: '0.1rem 0.4rem', borderRadius: 3, fontFamily: 'monospace', fontSize: '0.85rem',
  };
  const preStyle: React.CSSProperties = {
    background: '#f5f7fb', padding: '0.75rem 1rem', borderRadius: 6, fontFamily: 'monospace',
    fontSize: '0.82rem', overflowX: 'auto', lineHeight: 1.5,
  };

  return (
    <div style={{ maxWidth: 780 }}>
      <h1 style={{ margin: '0 0 1.5rem' }}>Help & Documentation</h1>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Getting Started</h2>
        <ol style={{ lineHeight: 1.8 }}>
          <li>Create an <strong>owner</strong> in the Management tab (e.g. your name or username).</li>
          <li>Optionally create additional <strong>profiles</strong> under that owner to separate collections (e.g. "foils", "vintage").</li>
          <li>Select your owner and profile in the sidebar — all data is scoped to this selection.</li>
          <li>Use the <strong>Search</strong> page to find cards and add them to your collection.</li>
        </ol>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Searching for Cards</h2>
        <p>Three game tabs are available: <strong>Magic: The Gathering</strong>, <strong>Pokémon</strong>, and <strong>Baseball Cards</strong>.</p>
        <ul style={{ lineHeight: 1.8 }}>
          <li><strong>MTG</strong> — searches Scryfall. Supports set hint (e.g. <code style={codeStyle}>M21</code>) and collector number.</li>
          <li><strong>Pokémon</strong> — searches the Pokemon TCG API. Supports set hint and card number.</li>
          <li><strong>Baseball</strong> — searches eBay and SportsCardDatabase. Provide player name, year, team, set, and/or card number.</li>
        </ul>
        <p>Results fall back to local cache when an API is unavailable or disabled in Settings.</p>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Adding Cards to Your Collection</h2>
        <p>
          On any search result card, enter the quantity and price you paid, choose a variant (foil, etched, etc. for MTG),
          then click <strong>Add</strong>. The card is added to the currently selected owner/profile.
        </p>
        <p>
          <strong>Duplicate strategy</strong> (configurable in Settings → General):
        </p>
        <ul style={{ lineHeight: 1.8 }}>
          <li><strong>Merge</strong> — adds quantities together when the same card+variant already exists.</li>
          <li><strong>Separate</strong> — keeps each addition as a distinct row.</li>
        </ul>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Importing a CSV</h2>
        <p>Go to <strong>Collection → Import/Export</strong> and upload a CSV file. The expected column format is:</p>
        <pre style={preStyle}>{`name,set_name,set_code,card_number,year,game,quantity,variant,
price_low,price_mid,price_market,price_usd,price_foil,price_etched,
paid,signed,altered,notes,link,image_url,timestamp`}</pre>
        <p>
          Cards that match multiple results in the database will be flagged as <strong>ambiguous</strong>.
          An ambiguity count is shown after import — resolve them via the Ambiguity Resolver (coming soon in the UI)
          or re-import with more specific data.
        </p>
        <p>
          The importer deduplicates on import: if a card with the same name/set/variant already exists, quantities are merged
          according to your duplicate strategy setting.
        </p>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Exporting Your Collection</h2>
        <ul style={{ lineHeight: 1.8 }}>
          <li><strong>Export CSV</strong> — exports the current owner/profile as a CSV with the same column schema as the import format.</li>
          <li><strong>Export ZIP</strong> — exports all profiles for the current owner as a ZIP of CSVs (one per profile/game).</li>
        </ul>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Investment Tracking</h2>
        <p>
          The <strong>Investment</strong> tab shows:
        </p>
        <ul style={{ lineHeight: 1.8 }}>
          <li><strong>Total Paid</strong> — sum of all <code style={codeStyle}>paid</code> values in your collection.</li>
          <li><strong>Market Value</strong> — sum of current market prices (updated when you search or refresh).</li>
          <li><strong>P&L</strong> — difference between market value and amount paid.</li>
          <li>Charts: value by game, and top sets by total value.</li>
        </ul>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Watchlist</h2>
        <p>
          Add cards you're watching (but haven't purchased) via the <strong>Add to Watchlist</strong> button on search results.
          Set a target price and monitor current market prices from the Watchlist tab.
        </p>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>Running the App Locally</h2>
        <p><strong>Backend (FastAPI):</strong></p>
        <pre style={preStyle}>{`cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
python migrations/csv_to_sqlite.py   # one-time migration
uvicorn main:app --reload --port 8000`}</pre>
        <p><strong>Frontend (React + Vite):</strong></p>
        <pre style={preStyle}>{`cd frontend
npm install
npm run dev   # starts on http://localhost:5173`}</pre>
      </div>

      <div style={sectionStyle}>
        <h2 style={h2Style}>API Keys</h2>
        <p>Configure these in <code style={codeStyle}>backend/.env</code>:</p>
        <ul style={{ lineHeight: 1.8, fontFamily: 'monospace', fontSize: '0.85rem' }}>
          <li><code style={codeStyle}>POKEMONTCG_API_KEY</code> — Pokemon TCG API (free tier works without a key)</li>
          <li><code style={codeStyle}>EBAY_APP_ID</code> — eBay Finding API (production)</li>
          <li><code style={codeStyle}>EBAY_APP_ID_SBX</code> — eBay Finding API (sandbox)</li>
          <li><code style={codeStyle}>JUSTTCG_API_KEY</code> — JustTCG pricing API</li>
        </ul>
        <p style={{ color: '#666', fontSize: '0.85rem' }}>
          All API calls are made server-side. Keys are never sent to the browser.
        </p>
      </div>
    </div>
  );
}
