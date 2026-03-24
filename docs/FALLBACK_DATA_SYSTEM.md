# Fallback Data System

## 🗂️ Directory Structure

```
fallback_data/
├── Pokemon/
│   ├── CardImages/          # Pokemon card images
│   ├── SetImages/           # Pokemon set logos
│   ├── pokemonsets.csv      # Pokemon sets data
│   └── pokemoncards.csv     # Pokemon cards data
└── MTG/
    ├── CardImages/          # MTG card images
    ├── SetImages/           # MTG set icons
    ├── mtgsets.csv          # MTG sets data
    └── mtgcards.csv         # MTG cards data
```

## 🎯 Purpose

**Build local fallback data automatically when API calls succeed:**
- ✅ **Offline functionality** - App works without internet
- ✅ **Faster responses** - Local data is instant
- ✅ **API quota preservation** - Fewer API calls needed
- ✅ **Data persistence** - Keep historical data even if APIs change

## 🔧 Implementation

### **1. Automatic Data Collection**

**Pokemon searches now automatically store:**
- Card data to `pokemoncards.csv`
- Set data to `pokemonsets.csv` 
- Card images to `Pokemon/CardImages/`
- Set logos to `Pokemon/SetImages/`

**MTG searches will store:**
- Card data to `mtgcards.csv`
- Set data to `mtgsets.csv`
- Card images to `MTG/CardImages/`
- Set icons to `MTG/SetImages/`

### **2. Fallback Manager Module** (`fallback_manager.py`)

**Key Functions:**
```python
# Store data from successful API calls
store_pokemon_card(card_data)
store_pokemon_set(set_data)
store_mtg_card(card_data)
store_mtg_set(set_data)

# Get statistics about cached data
get_fallback_stats()

# Download and cache images
download_image(url, save_path)
```

### **3. Data Storage Format**

**CSV files with comprehensive fields:**
- **Pokemon cards:** id, name, types, attacks, prices, images, etc.
- **Pokemon sets:** id, name, series, releaseDate, images, etc.
- **MTG cards:** id, name, set, mana_cost, prices, image_uris, etc.
- **MTG sets:** id, name, code, release_date, icon_svg_uri, etc.

**Images stored locally:**
- Pokemon: `{card_id}_small.png`, `{card_id}_large.png`
- MTG: `{card_id}_small.jpg`, `{card_id}_normal.jpg`, `{card_id}_large.jpg`
- Set images: `{set_id}_logo.png` or `{set_code}_icon.svg`

## 📊 Statistics Dashboard

**New sidebar section "📁 Fallback Data Stats" shows:**
- Number of cached sets and cards per game
- Number of downloaded images
- Real-time updates as data is collected

## 🚀 How It Works

### **First Search (Online):**
1. User searches for "Charizard"
2. API call succeeds → Returns card data
3. **Automatic storage:**
   - Card data saved to `pokemoncards.csv`
   - Set data saved to `pokemonsets.csv`
   - Images downloaded to local folders
4. Results displayed to user

### **Subsequent Searches (Offline/Online):**
1. User searches for "Charizard" again
2. Check local fallback data first
3. If found → **Instant results from local data**
4. If not found → Try API, then store results

### **Benefits:**
- 🚀 **Speed:** Local data loads instantly
- 💾 **Storage:** Build personal card database
- 🔄 **Reliability:** Works offline
- 💰 **Savings:** Fewer API calls over time

## 🧪 Testing the System

### **1. Check Initial State:**
- Open "📁 Fallback Data Stats" in sidebar
- Should show 0 for all counts

### **2. Perform Searches:**
- Search for Pokemon cards (with Pokemon TCG API enabled)
- Watch stats increase in real-time
- Check `fallback_data/` folder for new files

### **3. Verify Data Storage:**
```bash
# Check CSV files
cat tcgpricetracker/fallback_data/Pokemon/pokemoncards.csv
cat tcgpricetracker/fallback_data/Pokemon/pokemonsets.csv

# Check images
ls tcgpricetracker/fallback_data/Pokemon/CardImages/
ls tcgpricetracker/fallback_data/Pokemon/SetImages/
```

### **4. Offline Testing:**
- Disable internet/turn off API
- Search for previously cached cards
- Should get instant results from fallback data

## 🎯 Next Steps

### **Immediate:**
- ✅ Pokemon API data storage implemented
- ✅ Statistics dashboard added
- ✅ Image downloading implemented

### **Future Enhancements:**
- 🔄 **MTG data storage** - Add to Scryfall search function
- 🔍 **Fallback search** - Search local data when APIs fail
- 🗑️ **Data management** - Clean old data, set storage limits
- 📈 **Usage analytics** - Track cache hit rates
- 🔄 **Sync system** - Update stale data periodically

## 🎉 Result

**Automatic fallback data building is now active!** Every successful Pokemon search automatically builds your local card database for offline functionality and faster future searches.

**Your personal TCG database starts growing with every search!** 🗂️✨
