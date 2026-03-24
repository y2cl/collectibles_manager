# Clear Cache Button - Functionality Explained

## 🗑️ What Does the "Clear Cache" Button Do?

### **✅ Primary Function:**
The "Clear Cache" button on the sets page **deletes the cached sets data file**, forcing the application to fetch fresh data from the API on the next page load.

---

## 🔧 Technical Implementation

### **Code Logic:**
```python
# In ui_handlers.py (line 324-330):
if sets_data and st.button("🗑️ Clear Cache", key=f"clear_{game}_sets_page"):
    try:
        clear_cache_function(cache_file)  # Deletes the cache file
        st.success("Cache cleared!")
        st.rerun()  # Refreshes the page
    except Exception as e:
        st.error(f"Failed to clear cache: {e}")

# In tcgpricetracker.py (lines 693, 899):
clear_cache_function=lambda f: os.remove(f) if os.path.exists(f) else None
```

### **Cache Files Targeted:**
- **MTG Sets:** `mtg_sets_cache.json`
- **Pokemon Sets:** `pokemon_sets_cache.json`

---

## 📋 Step-by-Step Process

### **When You Click "🗑️ Clear Cache":**

1. **Check for Data:** Button only appears if sets data exists (`if sets_data`)
2. **Delete Cache File:** Removes the JSON cache file from disk
3. **Show Success:** Displays "Cache cleared!" message
4. **Refresh Page:** Automatically reloads the page (`st.rerun()`)
5. **Fetch Fresh Data:** On reload, cache is empty → API fetch triggered
6. **Update Display:** Shows fresh data from API

### **Error Handling:**
- **File Not Found:** Graceful handling if cache file doesn't exist
- **Permission Issues:** Shows error message if deletion fails
- **Network Issues:** Separate error handling for API fetch failures

---

## 🎯 User Experience

### **Before Clearing Cache:**
```
🃏 Magic: The Gathering Sets
┌─────────────────────────────────────────┐
│ [🔄 Update Sets] [🗑️ Clear Cache] [📥 Download] │
│                                         │
│ • Shows cached data from previous fetch  │
│ • Fast loading (from local cache)       │
│ • May show outdated information         │
└─────────────────────────────────────────┘
```

### **After Clearing Cache:**
```
🃏 Magic: The Gathering Sets
┌─────────────────────────────────────────┐
│ [🔄 Update Sets] [🗑️ Clear Cache] [📥 Download] │
│                                         │
│ ✅ Cache cleared!                      │
│                                         │
│ 🔄 Fetching MTG sets from Scryfall API... │
│ • Shows fresh data from API             │
│ • Slower loading (network request)      │
│ • Most up-to-date information          │
└─────────────────────────────────────────┘
```

---

## 🔄 Cache Lifecycle

### **Normal Operation:**
1. **First Visit:** No cache → API fetch → Store cache → Display data
2. **Subsequent Visits:** Cache exists → Load cache → Display data (fast)
3. **Update Sets:** Manual API fetch → Update cache → Display fresh data

### **With Clear Cache:**
1. **Clear Cache:** Delete cache file → Page reload
2. **No Cache:** API fetch → Store cache → Display fresh data
3. **Back to Normal:** Cache exists for future visits

---

## 📊 When to Use Clear Cache

### **✅ Use Cases:**
- **Data Issues:** Suspected corrupted or incomplete cache
- **Force Update:** Want to ensure absolutely latest data
- **Troubleshooting:** Debugging display or data problems
- **Testing:** Need fresh data for development/testing
- **Manual Refresh:** Prefer cache clear over "Update Sets"

### **⚠️ Considerations:**
- **Network Usage:** Triggers API call (uses bandwidth)
- **Loading Time:** Slower than normal cache loading
- **Rate Limits:** May hit API rate limits if used frequently
- **Data Freshness:** Usually not necessary if using "Update Sets"

---

## 🗂️ Cache File Details

### **File Locations:**
```
tcgpricetracker/
├── mtg_sets_cache.json          # MTG sets cache
└── pokemon_sets_cache.json      # Pokemon sets cache
```

### **Cache Content:**
```json
{
  "data": [
    {
      "id": "a90a7b2f-9dd8-4fc7-9f7d-8ea2797ec782",
      "name": "Throne of Eldraine",
      "code": "eld",
      "set_type": "expansion",
      "released_at": "2019-10-04",
      "card_count": 398,
      "digital": false,
      ...
    }
  ],
  "cached_at": "2026-03-20T16:27:00.000Z"
}
```

---

## 🆚 Clear Cache vs Update Sets

### **🗑️ Clear Cache:**
- **Action:** Delete cache → Force fresh fetch
- **Trigger:** Manual button click
- **Result:** Fresh API data on next page load
- **Use Case:** Troubleshooting, force refresh

### **🔄 Update Sets:**
- **Action:** Direct API fetch → Update cache
- **Trigger:** Manual button click
- **Result:** Fresh API data immediately
- **Use Case:** Normal data updates

### **Key Difference:**
- **Clear Cache:** Removes data → Next load fetches fresh
- **Update Sets:** Fetches fresh → Replaces existing data

---

## 🎉 Summary

**The "Clear Cache" button is a powerful tool for:**

- **🔧 Troubleshooting:** Fix data display issues
- **🔄 Force Refresh:** Ensure absolutely latest data
- **🧹 Cleanup:** Remove potentially corrupted cache
- **📊 Fresh Start:** Get clean slate from API

**It's essentially a "reset button" for the sets data, forcing the application to fetch everything fresh from the source API!** 🚀

### **Best Practice:**
- **Normal Updates:** Use "🔄 Update Sets" button
- **Troubleshooting:** Use "🗑️ Clear Cache" button
- **Data Issues:** Clear cache first, then update sets
