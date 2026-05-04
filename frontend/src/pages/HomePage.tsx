import { useState, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMtgSearch, usePokemonSearch, useCoinSearch, useComicSearch, useComicIssueSearch, useComicFindIssue, useForceRefreshSearch } from '../hooks/useSearch';
import type { CardResult } from '../types/card';
import { useAddCard } from '../hooks/useCollection';
import { useOwnerStore } from '../store/ownerStore';
import { lookupApi } from '../api/lookup';
import { collectionApi } from '../api/collection';
import ImagePicker from '../components/shared/ImagePicker';
import { gradingLookupUrl } from '../utils/gradingLookup';
import SearchResultsGrid from '../components/search/SearchResultsGrid';
import { useSettingsStore } from '../store/settingsStore';

type Game = 'mtg' | 'pokemon' | 'sports' | 'collectibles' | 'coins' | 'comics';

const TABS: { id: Game; label: string }[] = [
  { id: 'mtg',          label: '🧙 Magic: The Gathering' },
  { id: 'pokemon',      label: '⚡ Pokémon' },
  { id: 'sports',       label: '🏆 Sports Cards' },
  { id: 'collectibles', label: '🎁 Collectibles' },
  { id: 'coins',        label: '🪙 Coins' },
  { id: 'comics',       label: '📚 Comics' },
];

const SPORTS = [
  { value: 'baseball',   label: '⚾ Baseball' },
  { value: 'football',   label: '🏈 Football' },
  { value: 'basketball', label: '🏀 Basketball' },
  { value: 'hockey',     label: '🏒 Hockey' },
  { value: 'soccer',     label: '⚽ Soccer' },
  { value: 'other',      label: '🃏 Other' },
];

const CONDITIONS = ['New', 'Like New', 'Very Good', 'Good', 'Acceptable', 'Poor'];

const emptySportsForm = () => ({
  sport: 'baseball', player: '', cardNum: '', set: '', insert: '', year: '', printRun: '',
  gradingCompany: '', grade: '', serialNumber: '', signed: false, rc: false,
  paid: '', value: '', imageUrl: '',
});

const emptyCollectiblesForm = () => ({
  upc: '', name: '', series: '', manufacturer: '', year: '', condition: 'New', paid: '', value: '', imageUrl: '',
});

const emptyComicsForm = () => ({
  title: '', issueNumber: '', volume: '', writer: '', artist: '', publisher: '', year: '',
  gradingCompany: '', grade: '', cgcCertNumber: '', isKeyIssue: false,
  paid: '', value: '', imageUrl: '', storyArc: '',
});

export default function HomePage() {
  const [game, setGame] = useState<Game>('mtg');
  const { imageWidth } = useSettingsStore();
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const forceRefreshSearch = useForceRefreshSearch();
  const addCard = useAddCard();

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

  // Coins state
  const [coinName, setCoinName] = useState('');
  const [coinYear, setCoinYear] = useState('');
  const [coinMint, setCoinMint] = useState('');
  const [coinSearch, setCoinSearch] = useState(false);

  // Comics sub-mode: 'series' = browse flow, 'issue' = direct issue search
  const [comicMode, setComicMode] = useState<'series' | 'issue'>('series');
  // Comics — Browse Series (phase 1: volume search, phase 2: issue browse)
  const [comicName, setComicName] = useState('');
  const [comicSearch, setComicSearch] = useState(false);
  const [selectedVolume, setSelectedVolume] = useState<CardResult | null>(null);
  const [comicIssueFilter, setComicIssueFilter] = useState('');
  // Comics — Find Issue (direct: series name + issue number)
  const [findIssueName, setFindIssueName] = useState('');
  const [findIssueNumber, setFindIssueNumber] = useState('');
  const [findIssueSearch, setFindIssueSearch] = useState(false);

  // Comics manual-add state
  const [com, setCom] = useState(emptyComicsForm);
  const [comMsg, setComMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Sports manual-add state
  const [sp, setSp] = useState(emptySportsForm);
  const [spMsg, setSpMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [psaLoading, setPsaLoading] = useState(false);

  // Collectibles manual-add state
  const [col, setCol] = useState(emptyCollectiblesForm);
  const [colMsg, setColMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [upcLoading, setUpcLoading] = useState(false);
  const upcRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  // Autocomplete suggestions via React Query (proper caching + error visibility)
  const { data: suggestionsData } = useQuery({
    queryKey: ['suggestions', 'sports', currentOwnerId, currentProfileId],
    queryFn: () => collectionApi.suggestions(currentOwnerId!, currentProfileId || 'default', 'Sports Cards'),
    enabled: game === 'sports' && !!currentOwnerId,
    staleTime: 60 * 1000,
  });
  const spSuggestions = suggestionsData ?? { players: [], sets: [], inserts: [], grading_companies: [] };

  const setSp_ = (field: keyof ReturnType<typeof emptySportsForm>) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const value = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
      setSp((prev) => ({ ...prev, [field]: value }));
      setSpMsg(null);
    };

  const setCom_ = (field: keyof ReturnType<typeof emptyComicsForm>) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const value = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
      setCom((prev) => ({ ...prev, [field]: value }));
      setComMsg(null);
    };

  const setCol_ = (field: keyof ReturnType<typeof emptyCollectiblesForm>) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setCol((prev) => ({ ...prev, [field]: e.target.value }));
      setColMsg(null);
    };

  const mtgParams        = { name: mtgName, set_hint: mtgSet, collector_number: mtgNum };
  const pkmnParams       = { name: pkmnName, set_hint: pkmnSet, number: pkmnNum };
  const coinParams       = { name: coinName, year: coinYear, mint_mark: coinMint };
  const comicParams          = { name: comicName };
  const comicIssueParams     = { volume_id: selectedVolume?.set_code ?? '', issue_number: comicIssueFilter || undefined };
  const comicFindIssueParams = { name: findIssueName, issue_number: findIssueNumber };

  const mtgResult            = useMtgSearch(mtgParams, mtgSearch);
  const pkmnResult           = usePokemonSearch(pkmnParams, pkmnSearch);
  const coinResult           = useCoinSearch(coinParams, coinSearch);
  const comicResult          = useComicSearch(comicParams, comicSearch && !selectedVolume);
  const comicIssueResult     = useComicIssueSearch(comicIssueParams, !!selectedVolume);
  const comicFindIssueResult = useComicFindIssue(comicFindIssueParams, findIssueSearch);

  const handleAddSportsCard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sp.player.trim()) { setSpMsg({ ok: false, text: 'Player name is required.' }); return; }
    if (!currentOwnerId)   { setSpMsg({ ok: false, text: 'Select an owner first.' }); return; }
    try {
      await addCard.mutateAsync({
        owner_id: currentOwnerId, profile_id: currentProfileId,
        game: 'Sports Cards', sport: sp.sport,
        name: sp.player.trim(), card_number: sp.cardNum.trim(),
        set_name: sp.set.trim(), variant: sp.insert.trim(),
        year: sp.year.trim(),
        print_run: sp.printRun.trim() || undefined,
        grading_company: sp.gradingCompany.trim() || undefined,
        grade: sp.grade.trim() || undefined,
        serial_number: sp.serialNumber.trim() || undefined,
        signed: sp.signed ? 'true' : '',
        rc: sp.rc || undefined,
        image_url: sp.imageUrl || undefined,
        paid: parseFloat(sp.paid) || 0,
        price_usd: parseFloat(sp.value) || undefined,
      });
      setSpMsg({ ok: true, text: `Added ${sp.player} to collection!` });
      setSp(emptySportsForm);
      qc.invalidateQueries({ queryKey: ['suggestions', 'sports', currentOwnerId] });
    } catch {
      setSpMsg({ ok: false, text: 'Error adding card — try again.' });
    }
  };

  const handlePsaLookup = async () => {
    const cert = sp.serialNumber.trim();
    if (!cert) return;
    setPsaLoading(true);
    setSpMsg(null);
    try {
      const result = await lookupApi.psaCert(cert);
      setSp((prev) => ({
        ...prev,
        player:       result.player    || prev.player,
        year:         result.year      || prev.year,
        set:          result.set_name  || prev.set,
        cardNum:      result.card_number || prev.cardNum,
        grade:        result.grade     || prev.grade,
        gradingCompany: prev.gradingCompany || 'PSA',
      }));
      setSpMsg({ ok: true, text: `PSA cert found: ${result.subject || result.player}` });
    } catch {
      setSpMsg({ ok: false, text: 'PSA cert not found — check the number and try again.' });
    } finally {
      setPsaLoading(false);
    }
  };

  const handleUpcLookup = async () => {
    const code = col.upc.trim();
    if (!code) return;
    setUpcLoading(true);
    setColMsg(null);
    try {
      const result = await lookupApi.upc(code);
      setCol((prev) => ({
        ...prev,
        name:         result.name         || prev.name,
        manufacturer: result.manufacturer || prev.manufacturer,
        value:        result.price != null ? String(result.price) : prev.value,
      }));
      setColMsg({ ok: true, text: 'Auto-filled from barcode lookup.' });
    } catch {
      setColMsg({ ok: false, text: 'Barcode not found — fill in details manually.' });
    } finally {
      setUpcLoading(false);
    }
  };

  const handleAddCollectible = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!col.name.trim()) { setColMsg({ ok: false, text: 'Name is required.' }); return; }
    if (!currentOwnerId)  { setColMsg({ ok: false, text: 'Select an owner first.' }); return; }
    try {
      await addCard.mutateAsync({
        owner_id: currentOwnerId, profile_id: currentProfileId,
        game: 'Collectibles',
        name:         col.name.trim(),
        set_name:     col.series.trim(),
        manufacturer: col.manufacturer.trim(),
        year:         col.year.trim(),
        variant:      col.condition,
        upc:          col.upc.trim() || undefined,
        image_url:    col.imageUrl || undefined,
        paid:         parseFloat(col.paid) || 0,
        price_usd:    parseFloat(col.value) || undefined,
      });
      setColMsg({ ok: true, text: `Added "${col.name}" to collection!` });
      setCol(emptyCollectiblesForm);
    } catch {
      setColMsg({ ok: false, text: 'Error adding item — try again.' });
    }
  };

  const handleAddComic = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!com.title.trim()) { setComMsg({ ok: false, text: 'Title is required.' }); return; }
    if (!currentOwnerId)   { setComMsg({ ok: false, text: 'Select an owner first.' }); return; }
    try {
      await addCard.mutateAsync({
        owner_id: currentOwnerId, profile_id: currentProfileId,
        game: 'Comics',
        name: com.title.trim(),
        set_name: com.volume.trim(),
        year: com.year.trim(),
        issue_number: com.issueNumber.trim() || undefined,
        story_arc: com.storyArc.trim() || undefined,
        writer: com.writer.trim() || undefined,
        comic_artist: com.artist.trim() || undefined,
        publisher: com.publisher.trim() || undefined,
        grading_company: com.gradingCompany.trim() || undefined,
        grade: com.grade.trim() || undefined,
        cgc_cert_number: com.cgcCertNumber.trim() || undefined,
        is_key_issue: com.isKeyIssue || undefined,
        image_url: com.imageUrl || undefined,
        paid: parseFloat(com.paid) || 0,
        price_usd: parseFloat(com.value) || undefined,
      });
      setComMsg({ ok: true, text: `Added "${com.title}" #${com.issueNumber} to collection!` });
      setCom(emptyComicsForm);
    } catch {
      setComMsg({ ok: false, text: 'Error adding comic — try again.' });
    }
  };

  const inputStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.9rem', flex: 1,
  };
  const labelStyle: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.8rem', color: '#555', flex: 1,
  };
  const btnStyle: React.CSSProperties = {
    padding: '6px 16px', background: '#4c6ef5', color: '#fff',
    border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600,
  };
  const selectStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc',
    fontSize: '0.9rem', background: '#fff', cursor: 'pointer', width: '100%',
  };

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>➕ Add to Collection</h1>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '2px solid #e0e4ef', paddingBottom: '0.5rem', flexWrap: 'wrap' }}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setGame(id)}
            style={{
              padding: '6px 16px', borderRadius: '4px 4px 0 0', border: 'none',
              background: game === id ? '#4c6ef5' : '#f0f2fa',
              color: game === id ? '#fff' : '#333',
              fontWeight: game === id ? 700 : 400,
              cursor: 'pointer', fontSize: '0.9rem',
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

      {/* Coins Search */}
      {game === 'coins' && (
        <div>
          <p style={{ margin: '0 0 1rem', color: '#666', fontSize: '0.9rem' }}>
            Search the NGC Price Guide by coin type. Prices are fetched live and cached locally for faster future lookups.
          </p>
          <form
            onSubmit={(e) => { e.preventDefault(); setCoinSearch(true); }}
            style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1.5rem' }}
          >
            <input
              style={inputStyle}
              placeholder="Coin name / series *  (e.g. Morgan Dollar, Lincoln Cent)"
              value={coinName}
              onChange={(e) => { setCoinName(e.target.value); setCoinSearch(false); }}
            />
            <input
              style={{ ...inputStyle, flex: 0, width: 80 }}
              placeholder="Year"
              value={coinYear}
              onChange={(e) => { setCoinYear(e.target.value); setCoinSearch(false); }}
            />
            <input
              style={{ ...inputStyle, flex: 0, width: 70 }}
              placeholder="Mint"
              value={coinMint}
              onChange={(e) => { setCoinMint(e.target.value); setCoinSearch(false); }}
              title="Mint mark, e.g. D, S, O, CC"
            />
            <button type="submit" style={btnStyle}>Search Coins</button>
          </form>
          <SearchResultsGrid
            cards={coinResult.data?.cards ?? []}
            source={coinResult.data?.source}
            total={coinResult.data?.total}
            loading={coinResult.isLoading}
            imageWidth={imageWidth}
            onRefreshFromApi={() => forceRefreshSearch('coins', coinParams)}
          />
        </div>
      )}

      {/* Comics */}
      {game === 'comics' && (
        <div>
          {/* ── Sub-mode tabs ──────────────────────────────────────────────── */}
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
            {(['series', 'issue'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => {
                  setComicMode(mode);
                  setSelectedVolume(null);
                  setComicIssueFilter('');
                  setFindIssueSearch(false);
                }}
                style={{
                  padding: '5px 14px', borderRadius: 4, border: '1px solid',
                  borderColor: comicMode === mode ? '#4c6ef5' : '#ccc',
                  background: comicMode === mode ? '#4c6ef5' : '#f8f8f8',
                  color: comicMode === mode ? '#fff' : '#555',
                  fontWeight: comicMode === mode ? 600 : 400,
                  cursor: 'pointer', fontSize: '0.88rem',
                }}
              >
                {mode === 'series' ? '📖 Browse Series' : '🔍 Find Issue'}
              </button>
            ))}
          </div>

          {/* ── Find Issue mode ────────────────────────────────────────────── */}
          {comicMode === 'issue' && (
            <div>
              <p style={{ margin: '0 0 1rem', color: '#666', fontSize: '0.9rem' }}>
                Enter a series title and issue number to jump straight to a specific issue.
              </p>
              <form
                onSubmit={(e) => { e.preventDefault(); setFindIssueSearch(true); }}
                style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1.5rem' }}
              >
                <input
                  style={inputStyle}
                  placeholder="Series title *  (e.g. Action Comics)"
                  value={findIssueName}
                  onChange={(e) => { setFindIssueName(e.target.value); setFindIssueSearch(false); }}
                />
                <input
                  style={{ ...inputStyle, flex: 0, width: 110 }}
                  placeholder="Issue # *"
                  value={findIssueNumber}
                  onChange={(e) => { setFindIssueNumber(e.target.value); setFindIssueSearch(false); }}
                />
                <button type="submit" style={btnStyle}>Find Issue</button>
              </form>
              <SearchResultsGrid
                cards={comicFindIssueResult.data?.cards ?? []}
                source={comicFindIssueResult.data?.source}
                total={comicFindIssueResult.data?.total}
                loading={comicFindIssueResult.isLoading}
                imageWidth={imageWidth}
              />
              {comicFindIssueResult.data && comicFindIssueResult.data.cards.length === 0 && !comicFindIssueResult.isLoading && findIssueSearch && (
                <p style={{ color: '#888', fontSize: '0.9rem' }}>
                  No issues found for "{findIssueName}" #{findIssueNumber}. Try adjusting the series title.
                </p>
              )}
            </div>
          )}

          {/* ── Browse Series mode ─────────────────────────────────────────── */}
          {comicMode === 'series' && (
          <div>
          {/* ── Phase 1: Series search (no volume selected) ────────────────── */}
          {!selectedVolume && (
            <div>
              <p style={{ margin: '0 0 1rem', color: '#666', fontSize: '0.9rem' }}>
                Search for a series by title, then browse its issues.
                Requires a Comic Vine API key in <code>backend/.env</code>.
              </p>
              <form
                onSubmit={(e) => { e.preventDefault(); setComicSearch(true); }}
                style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1.5rem' }}
              >
                <input
                  style={inputStyle}
                  placeholder="Series title *  (e.g. Action Comics, Amazing Spider-Man)"
                  value={comicName}
                  onChange={(e) => { setComicName(e.target.value); setComicSearch(false); }}
                />
                <button type="submit" style={btnStyle}>Search Series</button>
              </form>

              {/* Volume (series) results list */}
              {comicResult.isLoading && <p style={{ color: '#888' }}>Searching…</p>}
              {comicResult.data && comicResult.data.cards.length === 0 && (
                <p style={{ color: '#888', fontSize: '0.9rem' }}>
                  No series found. Check your API key or try a different title.
                </p>
              )}
              {(comicResult.data?.cards ?? []).length > 0 && (
                <div>
                  <p style={{ margin: '0 0 0.75rem', color: '#888', fontSize: '0.82rem' }}>
                    {comicResult.data!.cards.length} series found — click one to browse its issues
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                    {comicResult.data!.cards.map((vol, i) => (
                      <div
                        key={vol.set_code || i}
                        style={{
                          display: 'flex', gap: 12, alignItems: 'center',
                          padding: '10px 8px', borderBottom: '1px solid #eee',
                          borderRadius: 4, cursor: 'default',
                        }}
                      >
                        {vol.image_url && (
                          <img
                            src={vol.image_url}
                            alt=""
                            style={{ width: 44, height: 62, objectFit: 'cover', borderRadius: 2, flexShrink: 0 }}
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                          />
                        )}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <strong style={{ fontSize: '0.95rem' }}>{vol.name}</strong>
                          {vol.set_name && (
                            <span style={{ color: '#666', marginLeft: 8, fontSize: '0.88rem' }}>{vol.set_name}</span>
                          )}
                          {vol.year && (
                            <span style={{ color: '#999', marginLeft: 6, fontSize: '0.85rem' }}>({vol.year})</span>
                          )}
                          {vol.card_number && (
                            <span style={{ color: '#aaa', marginLeft: 8, fontSize: '0.8rem' }}>
                              {vol.card_number} issues
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => {
                            setSelectedVolume(vol);
                            setComicIssueFilter('');
                          }}
                          style={{ ...btnStyle, whiteSpace: 'nowrap', flexShrink: 0 }}
                        >
                          Browse Issues →
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Phase 2: Issues for selected volume ────────────────────────── */}
          {selectedVolume && (
            <div>
              {/* Selected series header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: '1rem', flexWrap: 'wrap' }}>
                <button
                  onClick={() => { setSelectedVolume(null); setComicIssueFilter(''); }}
                  style={{ padding: '5px 12px', borderRadius: 4, border: '1px solid #ccc', background: '#f8f8f8', cursor: 'pointer', fontSize: '0.85rem' }}
                >
                  ← Back to series
                </button>
                {selectedVolume.image_url && (
                  <img
                    src={selectedVolume.image_url}
                    alt=""
                    style={{ width: 36, height: 50, objectFit: 'cover', borderRadius: 2 }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                )}
                <div>
                  <strong style={{ fontSize: '1.05rem' }}>{selectedVolume.name}</strong>
                  {selectedVolume.set_name && <span style={{ color: '#666', marginLeft: 8 }}>{selectedVolume.set_name}</span>}
                  {selectedVolume.year && <span style={{ color: '#999', marginLeft: 6 }}>({selectedVolume.year})</span>}
                  {selectedVolume.card_number && (
                    <span style={{ color: '#aaa', marginLeft: 8, fontSize: '0.85rem' }}>
                      {selectedVolume.card_number} issues
                    </span>
                  )}
                </div>
              </div>

              {/* Issue number filter */}
              <div style={{ display: 'flex', gap: 8, marginBottom: '1.5rem', alignItems: 'center' }}>
                <input
                  style={{ ...inputStyle, flex: 0, width: 120 }}
                  placeholder="Filter by issue #"
                  value={comicIssueFilter}
                  onChange={(e) => setComicIssueFilter(e.target.value)}
                  title="Enter an issue number to jump to a specific issue"
                />
                {comicIssueFilter && (
                  <button
                    onClick={() => setComicIssueFilter('')}
                    style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', background: '#f8f8f8', cursor: 'pointer', fontSize: '0.85rem' }}
                  >
                    Clear
                  </button>
                )}
                {comicIssueResult.isLoading && <span style={{ color: '#888', fontSize: '0.85rem' }}>Loading issues…</span>}
              </div>

              {/* Issues grid */}
              <SearchResultsGrid
                cards={comicIssueResult.data?.cards ?? []}
                source={comicIssueResult.data?.source}
                total={comicIssueResult.data?.total}
                loading={comicIssueResult.isLoading}
                imageWidth={imageWidth}
              />
              {comicIssueResult.data && comicIssueResult.data.cards.length === 0 && !comicIssueResult.isLoading && (
                <p style={{ color: '#888', fontSize: '0.9rem' }}>
                  No issues found{comicIssueFilter ? ` for issue #${comicIssueFilter}` : ''}.
                </p>
              )}
            </div>
          )}
          </div>
          )}

          {/* ── Manual add form ─────────────────────────────────────────────── */}
          <div style={{ borderTop: '2px solid #e0e4ef', margin: '2rem 0 1.5rem' }} />
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', color: '#333' }}>Add Comic Manually</h3>
          <form onSubmit={handleAddComic} style={{ maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 12 }}>

            {/* Title | Issue # */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={labelStyle}>
                Title / Series *
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.title} onChange={setCom_('title')} placeholder="e.g. Amazing Spider-Man" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 90px' }}>
                Issue #
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.issueNumber} onChange={setCom_('issueNumber')} placeholder="e.g. 300" />
              </label>
            </div>

            {/* Volume | Year | Publisher */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={labelStyle}>
                Volume / Series
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.volume} onChange={setCom_('volume')} placeholder="e.g. Vol. 1" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 100px' }}>
                Year
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.year} onChange={setCom_('year')} placeholder="e.g. 1988" />
              </label>
              <label style={labelStyle}>
                Publisher
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.publisher} onChange={setCom_('publisher')} placeholder="e.g. Marvel" />
              </label>
            </div>

            {/* Story Arc */}
            <label style={labelStyle}>
              Story Arc / Issue Title
              <input style={{ ...inputStyle, flex: 'unset' }} value={com.storyArc} onChange={setCom_('storyArc')} placeholder="e.g. Kraven's Last Hunt" />
            </label>

            {/* Writer | Artist */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={labelStyle}>
                Writer
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.writer} onChange={setCom_('writer')} placeholder="e.g. Stan Lee" />
              </label>
              <label style={labelStyle}>
                Artist / Penciler
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.artist} onChange={setCom_('artist')} placeholder="e.g. Steve Ditko" />
              </label>
            </div>

            {/* Grading Company | Grade | CGC Cert | Key Issue */}
            <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end' }}>
              <label style={labelStyle}>
                Grading Company
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.gradingCompany} onChange={setCom_('gradingCompany')} placeholder="e.g. CGC, CBCS" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 100px' }}>
                Grade
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.grade} onChange={setCom_('grade')} placeholder="e.g. 9.8" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 160px' }}>
                CGC/CBCS Cert #
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.cgcCertNumber} onChange={setCom_('cgcCertNumber')} placeholder="e.g. 4003298001" />
              </label>
              <label style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 8, fontSize: '0.9rem', color: '#555', paddingBottom: 7, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                <input type="checkbox" checked={com.isKeyIssue} onChange={setCom_('isKeyIssue')} style={{ width: 16, height: 16, cursor: 'pointer' }} />
                Key Issue
              </label>
            </div>

            {/* Price Paid | Value */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={{ ...labelStyle, flex: '0 0 140px' }}>
                Price Paid ($)
                <input type="number" min={0} step={0.01} style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.paid} onChange={setCom_('paid')} placeholder="0.00" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 140px' }}>
                Value ($)
                <input type="number" min={0} step={0.01} style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={com.value} onChange={setCom_('value')} placeholder="0.00" />
              </label>
            </div>

            {/* Image picker */}
            <div>
              <span style={{ fontSize: '0.8rem', color: '#555', display: 'block', marginBottom: 6 }}>Cover Image</span>
              <ImagePicker
                query={[com.title, com.issueNumber, com.publisher, 'comic cover'].filter(Boolean).join(' ')}
                selectedUrl={com.imageUrl}
                onSelect={(url) => setCom((prev) => ({ ...prev, imageUrl: url }))}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button type="submit" style={btnStyle} disabled={addCard.isPending}>
                {addCard.isPending ? 'Adding…' : '+ Add to Collection'}
              </button>
              {comMsg && <span style={{ fontSize: '0.85rem', color: comMsg.ok ? '#2a7a2a' : '#c00' }}>{comMsg.text}</span>}
            </div>
          </form>
        </div>
      )}

      {/* Sports Cards — manual entry */}
      {game === 'sports' && (
        <div style={{ maxWidth: 860 }}>
          <form onSubmit={handleAddSportsCard} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Row: Sport */}
            <label style={{ ...labelStyle, maxWidth: 260 }}>
              Sport
              <select style={selectStyle} value={sp.sport} onChange={setSp_('sport')}>
                {SPORTS.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>

            {/* Datalists for autocomplete */}
            <datalist id="sp-players">{spSuggestions.players.map(v => <option key={v} value={v} />)}</datalist>
            <datalist id="sp-sets">{spSuggestions.sets.map(v => <option key={v} value={v} />)}</datalist>
            <datalist id="sp-inserts">{spSuggestions.inserts.map(v => <option key={v} value={v} />)}</datalist>
            <datalist id="sp-grading">{spSuggestions.grading_companies.map(v => <option key={v} value={v} />)}</datalist>

            {/* Row: Player Name | Card # */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={labelStyle}>
                Player Name *
                <input list="sp-players" style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.player} onChange={setSp_('player')} placeholder="e.g. Mike Trout" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 130px' }}>
                Card #
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.cardNum} onChange={setSp_('cardNum')} placeholder="e.g. 123" />
              </label>
            </div>

            {/* Row: Year | Set | Insert | Serial # */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={{ ...labelStyle, flex: '0 0 100px' }}>
                Year
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.year} onChange={setSp_('year')} placeholder="e.g. 2024" />
              </label>
              <label style={labelStyle}>
                Set
                <input list="sp-sets" style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.set} onChange={setSp_('set')} placeholder="e.g. 2024 Topps Series 1" />
              </label>
              <label style={labelStyle}>
                Insert
                <input list="sp-inserts" style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.insert} onChange={setSp_('insert')} placeholder="e.g. Refractor, Auto, Base" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 110px' }}>
                Serial #
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.printRun} onChange={setSp_('printRun')} placeholder="e.g. 23/99" />
              </label>
            </div>

            {/* Row: Grading Company | Grade | Cert. Number | Signed */}
            <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end' }}>
              <label style={labelStyle}>
                Grading Company
                <input list="sp-grading" style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.gradingCompany} onChange={setSp_('gradingCompany')} placeholder="e.g. PSA, BGS, SGC" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 100px' }}>
                Grade
                <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.grade} onChange={setSp_('grade')} placeholder="e.g. 9.5" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 140px' }}>
                Cert. Number
                <div style={{ display: 'flex', gap: 6 }}>
                  <input style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.serialNumber} onChange={setSp_('serialNumber')} placeholder="e.g. 12345678" />
                  {sp.gradingCompany.toLowerCase().includes('psa') && sp.serialNumber.trim() && (
                    <button
                      type="button"
                      onClick={handlePsaLookup}
                      disabled={psaLoading}
                      style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #4c6ef5', background: '#4c6ef5', color: '#fff', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
                    >
                      {psaLoading ? '…' : 'Lookup'}
                    </button>
                  )}
                </div>
              </label>
              <label style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 8, fontSize: '0.9rem', color: '#555', paddingBottom: 7, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                <input type="checkbox" checked={sp.signed} onChange={setSp_('signed')} style={{ width: 16, height: 16, cursor: 'pointer' }} />
                Signed
              </label>
              <label style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 8, fontSize: '0.9rem', color: '#555', paddingBottom: 7, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                <input type="checkbox" checked={sp.rc} onChange={setSp_('rc')} style={{ width: 16, height: 16, cursor: 'pointer' }} />
                RC
              </label>
            </div>
            {gradingLookupUrl(sp.gradingCompany, sp.serialNumber) && (
              <div style={{ fontSize: '0.82rem' }}>
                <a
                  href={gradingLookupUrl(sp.gradingCompany, sp.serialNumber)!}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: '#4c6ef5', textDecoration: 'none' }}
                >
                  🔍 Look up cert #{sp.serialNumber} on {sp.gradingCompany} →
                </a>
              </div>
            )}

            {/* Row: Price Paid | Value */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={{ ...labelStyle, flex: '0 0 140px' }}>
                Price Paid ($)
                <input type="number" min={0} step={0.01} style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.paid} onChange={setSp_('paid')} placeholder="0.00" />
              </label>
              <label style={{ ...labelStyle, flex: '0 0 140px' }}>
                Value ($)
                <input type="number" min={0} step={0.01} style={{ ...inputStyle, flex: 'unset', width: '100%' }} value={sp.value} onChange={setSp_('value')} placeholder="0.00" />
              </label>
              <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 7 }}>
                <span style={{ fontSize: '0.75rem', color: '#aaa' }}>eBay lookup coming soon</span>
              </div>
            </div>

            {/* Image search / upload */}
            <div>
              <span style={{ fontSize: '0.8rem', color: '#555', display: 'block', marginBottom: 6 }}>Image</span>
              <ImagePicker
                query={[sp.player, sp.year, sp.set, sp.sport, 'card'].filter(Boolean).join(' ')}
                selectedUrl={sp.imageUrl}
                onSelect={(url) => setSp((prev) => ({ ...prev, imageUrl: url }))}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 4 }}>
              <button type="submit" style={btnStyle} disabled={addCard.isPending}>
                {addCard.isPending ? 'Adding…' : '+ Add to Collection'}
              </button>
              {spMsg && <span style={{ fontSize: '0.85rem', color: spMsg.ok ? '#2a7a2a' : '#c00' }}>{spMsg.text}</span>}
            </div>
          </form>
        </div>
      )}

      {/* Collectibles — manual entry with UPC lookup */}
      {game === 'collectibles' && (
        <div style={{ maxWidth: 560 }}>
          <p style={{ margin: '0 0 1rem', color: '#666', fontSize: '0.9rem' }}>
            Scan or enter a barcode to auto-fill details, or fill in manually.
          </p>
          <form onSubmit={handleAddCollectible} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

            {/* UPC barcode lookup */}
            <label style={labelStyle}>
              Barcode (UPC/EAN)
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  ref={upcRef}
                  style={{ ...inputStyle, flex: 'unset', flexGrow: 1 }}
                  value={col.upc}
                  onChange={setCol_('upc')}
                  placeholder="e.g. 035112482597"
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleUpcLookup(); } }}
                />
                <button
                  type="button"
                  onClick={handleUpcLookup}
                  disabled={upcLoading || !col.upc.trim()}
                  style={{ ...btnStyle, background: '#6c757d', whiteSpace: 'nowrap' }}
                >
                  {upcLoading ? 'Looking up…' : '🔍 Lookup'}
                </button>
              </div>
              {colMsg && (
                <span style={{ fontSize: '0.8rem', color: colMsg.ok ? '#2a7a2a' : '#888', marginTop: 2 }}>
                  {colMsg.text}
                </span>
              )}
            </label>

            <div style={{ borderTop: '1px solid #eee', paddingTop: 12 }} />

            {/* Name */}
            <label style={labelStyle}>
              Name *
              <input style={{ ...inputStyle, flex: 'unset' }} value={col.name} onChange={setCol_('name')} placeholder="e.g. Optimus Prime G1 Reissue" />
            </label>

            {/* Line / Series */}
            <label style={labelStyle}>
              Line / Series
              <input style={{ ...inputStyle, flex: 'unset' }} value={col.series} onChange={setCol_('series')} placeholder="e.g. Transformers Studio Series" />
            </label>

            {/* Manufacturer */}
            <label style={labelStyle}>
              Manufacturer
              <input style={{ ...inputStyle, flex: 'unset' }} value={col.manufacturer} onChange={setCol_('manufacturer')} placeholder="e.g. Hasbro" />
            </label>

            {/* Year */}
            <label style={labelStyle}>
              Year
              <input style={{ ...inputStyle, flex: 'unset', width: 100 }} value={col.year} onChange={setCol_('year')} placeholder="e.g. 2023" />
            </label>

            {/* Condition */}
            <label style={labelStyle}>
              Condition
              <select style={selectStyle} value={col.condition} onChange={setCol_('condition')}>
                {CONDITIONS.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>

            {/* Price Paid / Value */}
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={labelStyle}>
                Price Paid ($)
                <input type="number" min={0} step={0.01} style={{ ...inputStyle, flex: 'unset', width: 120 }} value={col.paid} onChange={setCol_('paid')} placeholder="0.00" />
              </label>
              <label style={labelStyle}>
                Value ($)
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input type="number" min={0} step={0.01} style={{ ...inputStyle, flex: 'unset', width: 120 }} value={col.value} onChange={setCol_('value')} placeholder="0.00" />
                  <span style={{ fontSize: '0.75rem', color: '#aaa', whiteSpace: 'nowrap' }}>eBay lookup soon</span>
                </div>
              </label>
            </div>

            {/* Image picker */}
            <div>
              <span style={{ fontSize: '0.8rem', color: '#555', display: 'block', marginBottom: 6 }}>Image</span>
              <ImagePicker
                query={[col.name, col.manufacturer, col.series, 'collectible'].filter(Boolean).join(' ')}
                selectedUrl={col.imageUrl}
                onSelect={(url) => setCol((prev) => ({ ...prev, imageUrl: url }))}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button type="submit" style={btnStyle} disabled={addCard.isPending}>
                {addCard.isPending ? 'Adding…' : '+ Add to Collection'}
              </button>
            </div>

          </form>
        </div>
      )}

      {/* Search Results */}
      {game === 'mtg' && (
        <SearchResultsGrid
          cards={mtgResult.data?.cards ?? []}
          source={mtgResult.data?.source}
          total={mtgResult.data?.total}
          loading={mtgResult.isLoading}
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
          imageWidth={imageWidth}
          onRefreshFromApi={() => forceRefreshSearch('pokemon', pkmnParams)}
        />
      )}
    </div>
  );
}
