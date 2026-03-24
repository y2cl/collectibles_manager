# DRY (Don't Repeat Yourself) Analysis and Refactoring Plan

## Current DRY Violations Identified:

### 1. **"Add to Collection" Button Duplication** (5+ occurrences)
**Problem:** Nearly identical code repeated for:
- MTG Grid view
- MTG List view  
- Pokémon Grid view
- Pokémon List view
- Watchlist items

**Current Pattern:**
```python
# Repeated 5+ times with minor variations:
ql.markdown("Qty")
qty = qi.number_input("Quantity", min_value=1, max_value=999, value=1, step=1, key=f"qty_...")
if act_cols[1].button("Add to collection", key=f"add_..."):
    ok, msg = add_to_collection(
        game="...",
        name=...,
        set_name=...,
        # ... repeated parameters
    )
```

**Solution:** ✅ Created `render_add_to_collection_button()` in `ui_handlers.py`

---

### 2. **Duplicate MTG Sets Pages** (2 complete duplicates)
**Problem:** Entire MTG sets page code duplicated at lines ~656 and ~1123

**Current Pattern:**
```python
# Duplicate 1:
st.write("**All Magic: The Gathering Sets:**")
search_term = st.text_input("🔍 Search sets", ...)
# ... 50+ lines of identical code

# Duplicate 2: 
st.write("**All Magic: The Gathering Sets:**")
search_term = st.text_input("🔍 Search sets", ...)
# ... 50+ lines of identical code
```

**Solution:** ✅ Created `render_sets_page()` in `ui_handlers.py`

---

### 3. **Hardcoded Constants Scattered Throughout**
**Problem:** Magic numbers and strings repeated across the file

**Examples:**
- `CARD_IMAGE_WIDTH = 200` used in multiple places
- Game names "Magic: The Gathering", "Pokémon" hardcoded
- File names "tcg_collection.csv", "pokemon_sets_cache.json" repeated
- Quantity range (1, 999) repeated
- Button keys patterns repeated

**Solution:** ✅ Created `constants.py` with centralized configuration

---

### 4. **Price Display Logic Duplication**
**Problem:** Similar price display code for MTG and Pokémon

**Current Pattern:**
```python
# MTG version:
pcols = st.columns(3)
pcols[0].metric("USD", f"{ps['usd']:.2f} USD" if ps["usd"] is not None else "-")
pcols[1].metric("USD Foil", f"{ps['usd_foil']:.2f} USD" if ps["usd_foil"] is not None else "-")
pcols[2].metric("USD Etched", f"{ps['usd_etched']:.2f} USD" if ps["usd_etched"] is not None else "-")

# Pokémon version:
pcols = st.columns(3)
pcols[0].metric("Low", f"${ps['low']:.2f}" if ps["low"] is not None else "-")
pcols[1].metric("Mid", f"${ps['mid']:.2f}" if ps["mid"] is not None else "-")
pcols[2].metric("Market", f"${ps['market']:.2f}" if ps["market"] is not None else "-")
```

**Solution:** ✅ Created `render_card_price_display()` in `ui_handlers.py`

---

### 5. **Session State Key Duplication**
**Problem:** Session state keys hardcoded throughout the file

**Examples:**
- `"show_collection_view"` used in multiple places
- `"api_settings"` repeated
- `"debug_mode"` scattered

**Solution:** ✅ Centralized in `constants.py` under `SESSION_KEYS`

---

### 6. **Navigation Button Duplication**
**Problem:** "Back to search" button logic repeated

**Current Pattern:**
```python
# Repeated multiple times:
if st.button("Back to search"):
    st.session_state["show_collection_view"] = False
    st.session_state["show_sets_view"] = False
    st.session_state["show_mtg_sets_view"] = False
    st.rerun()
```

**Solution:** ✅ Created `render_navigation_buttons()` in `ui_handlers.py`

---

## Refactoring Benefits:

### **Code Reduction:**
- **Before:** ~2400 lines with significant duplication
- **After:** Estimated ~1800 lines + reusable modules

### **Maintainability:**
- ✅ Single source of truth for constants
- ✅ Reusable UI components
- ✅ Consistent behavior across all views
- ✅ Easier to add new features

### **Bug Prevention:**
- ✅ Fix once, applies everywhere
- ✅ Consistent validation and error handling
- ✅ Standardized user experience

### **Future Extensibility:**
- ✅ Easy to add new games (Yu-Gi-Oh, etc.)
- ✅ Simple to modify UI patterns
- ✅ Configurable behavior via constants

## Next Steps:

1. **Update main file** to use new handlers and constants
2. **Remove duplicate code** (especially MTG sets pages)
3. **Standardize all "Add to collection" buttons**
4. **Add Scryfall links** using the new clean structure
5. **Test all functionality** to ensure no regressions

## Files Created:
- ✅ `constants.py` - Centralized configuration
- ✅ `ui_handlers.py` - Reusable UI components  
- ✅ `DRY_ANALYSIS.md` - This analysis document

## Files to Refactor:
- 🔄 `tcgpricetracker.py` - Main file (remove duplications, use handlers)
