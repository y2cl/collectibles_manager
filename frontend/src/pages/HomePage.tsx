import { useState } from 'react';
import { useMtgSearch, usePokemonSearch, useBaseballSearch, useForceRefreshSearch } from '../hooks/useSearch';
import SearchResultsGrid from '../components/search/SearchResultsGrid';
import { useSettingsStore } from '../store/settingsStore';

type Game = 'mtg' | 'pokemon' | 'baseball';

const TABS: { id: Game; label: string }[] = [
  { id: 'mtg', label: '🧙 Magic: The Gathering' },
  { id: 'pokemon', label: '⚡ Pokémon' },
  { id: 'baseball', label: '⚾ Baseball Cards' },
];

export default function HomePage() {
  const [game, setGame] = useState<Game>('mtg');
  const { cardsPerRow, imageWidth } = useSettingsStore();
  const forceRefreshSearch = useForceRefreshSearch();

  // MTG state
  const [mtgName, setMtgName] = useState('');
  const [mtgSet, setMtgSet] = useState('');
  const [mtgNum, setMtgNum] = useState('');
  const [mtgSearch, setMtgSearch] = useState(false);

  // Pokémon state
  const [pkmnName, setPkmnName] = useState('');
  const [pkmnSet, setPkmnSet] = useState('');
  const [pkmnNum, setPkmnNum] = useState('');
  const [pkmnSearch, setPkmnSearch] = useState(false);

  // Baseball state
  const [bsPlayer, setBsPlayer] = useState('');
  const [bsYear, setBsYear] = useState('');
  const [bsTeam, setBsTeam] = useState('');
  const [bsSet, setBsSet] = useState('');
  const [bsNum, setBsNum] = useState('');
  const [bsSearch, setBsSearch] = useState(false);

  // Current params (needed for force-refresh callbacks)
  const mtgParams = { name: mtgName, set_hint: mtgSet, collector_number: mtgNum };
  const pkmnParams = { name: pkmnName, set_hint: pkmnSet, number: pkmnNum };
  const bsParams   = { player_name: bsPlayer, year: bsYear, team: bsTeam, set_name: bsSet, card_number: bsNum };

  const mtgResult  = useMtgSearch(mtgParams, mtgSearch);
  const pkmnResult = usePokemonSearch(pkmnParams, pkmnSearch);
  const bsResult   = useBaseballSearch(bsParams, bsSearch);

  const inputStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc',
    fontSize: '0.9rem', flex: 1,
  };
  const btnStyle: React.CSSProperties = {
    padding: '6px 16px', background: '#4c6ef5', color: '#fff',
    border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600,
  };

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>🔍 Search Cards</h1>

      {/* Game tab bar */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '2px solid #e0e4ef', paddingBottom: '0.5rem' }}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setGame(id)}
            style={{
              padding: '6px 16px',
              borderRadius: '4px 4px 0 0',
              border: 'none',
              background: game === id ? '#4c6ef5' : '#f0f2fa',
              color: game === id ? '#fff' : '#333',
              fontWeight: game === id ? 700 : 400,
              cursor: 'pointer',
              fontSize: '0.9rem',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* MTG Search */}
      {game === 'mtg' && (
        <form
          onSubmit={(e) => { e.preventDefault(); setMtgSearch(true); }}
          style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1.5rem' }}
        >
          <input style={inputStyle} placeholder="Card name *" value={mtgName}
            onChange={(e) => { setMtgName(e.target.value); setMtgSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 120 }} placeholder="Set hint" value={mtgSet}
            onChange={(e) => { setMtgSet(e.target.value); setMtgSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 80 }} placeholder="# number" value={mtgNum}
            onChange={(e) => { setMtgNum(e.target.value); setMtgSearch(false); }} />
          <button type="submit" style={btnStyle}>Search MTG</button>
        </form>
      )}

      {/* Pokémon Search */}
      {game === 'pokemon' && (
        <form
          onSubmit={(e) => { e.preventDefault(); setPkmnSearch(true); }}
          style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1.5rem' }}
        >
          <input style={inputStyle} placeholder="Card name *" value={pkmnName}
            onChange={(e) => { setPkmnName(e.target.value); setPkmnSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 120 }} placeholder="Set name/code" value={pkmnSet}
            onChange={(e) => { setPkmnSet(e.target.value); setPkmnSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 80 }} placeholder="Card #" value={pkmnNum}
            onChange={(e) => { setPkmnNum(e.target.value); setPkmnSearch(false); }} />
          <button type="submit" style={btnStyle}>Search Pokémon</button>
        </form>
      )}

      {/* Baseball Search */}
      {game === 'baseball' && (
        <form
          onSubmit={(e) => { e.preventDefault(); setBsSearch(true); }}
          style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1.5rem' }}
        >
          <input style={inputStyle} placeholder="Player name *" value={bsPlayer}
            onChange={(e) => { setBsPlayer(e.target.value); setBsSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 80 }} placeholder="Year" value={bsYear}
            onChange={(e) => { setBsYear(e.target.value); setBsSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 100 }} placeholder="Team" value={bsTeam}
            onChange={(e) => { setBsTeam(e.target.value); setBsSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 120 }} placeholder="Set name" value={bsSet}
            onChange={(e) => { setBsSet(e.target.value); setBsSearch(false); }} />
          <input style={{ ...inputStyle, flex: 0, width: 80 }} placeholder="Card #" value={bsNum}
            onChange={(e) => { setBsNum(e.target.value); setBsSearch(false); }} />
          <button type="submit" style={btnStyle}>Search Baseball</button>
        </form>
      )}

      {/* Results */}
      {game === 'mtg' && (
        <SearchResultsGrid
          cards={mtgResult.data?.cards ?? []}
          source={mtgResult.data?.source}
          total={mtgResult.data?.total}
          loading={mtgResult.isLoading}
          cardsPerRow={cardsPerRow}
          imageWidth={imageWidth}
          onRefreshFromApi={() => forceRefreshSearch('mtg', mtgParams)}
        />
      )}
      {game === 'pokemon' && (
        <SearchResultsGrid
          cards={pkmnResult.data?.cards ?? []}
          source={pkmnResult.data?.source}
          total={pkmnResult.data?.total}
          loading={pkmnResult.isLoading}
          cardsPerRow={cardsPerRow}
          imageWidth={imageWidth}
          onRefreshFromApi={() => forceRefreshSearch('pokemon', pkmnParams)}
        />
      )}
      {game === 'baseball' && (
        <SearchResultsGrid
          cards={bsResult.data?.cards ?? []}
          source={bsResult.data?.source}
          total={bsResult.data?.total}
          loading={bsResult.isLoading}
          cardsPerRow={cardsPerRow}
          imageWidth={imageWidth}
          onRefreshFromApi={() => forceRefreshSearch('baseball', bsParams)}
        />
      )}
    </div>
  );
}
