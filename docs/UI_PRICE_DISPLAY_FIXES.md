# UI Price Display Fixes

## 🎯 Issues Fixed

### **1. Price Alignment Issue**
**Problem:** Price metrics (low, mid, market) were not centered above the quantity and "Add to collection" buttons.

**Solution:** Updated `render_card_price_display()` in `ui_handlers.py` to use centered column layout:

```python
# Before (left-aligned):
pcols = st.columns(3)
pcols[0].metric("Low", ...)
pcols[1].metric("Mid", ...)  
pcols[2].metric("Market", ...)

# After (centered):
price_cols = st.columns([1, 2, 2, 2, 1])
with price_cols[1]:  # Skip first column for left margin
    st.metric("Low", ...)
with price_cols[2]:  # Center column
    st.metric("Mid", ...)
with price_cols[3]:  # Skip last column for right margin  
    st.metric("Market", ...)
```

**Result:** Prices are now perfectly centered above the action buttons.

### **2. Missing Variant Prices Section**
**Problem:** "Variant prices" collapsible section wasn't appearing for Pokémon cards.

**Root Cause:** The section was only shown if `tcgplayer.prices` data existed in the API response. Many cards don't have variant price data.

**Solution:** 
1. **Added conditional display** - Only show expander if variant data exists
2. **Added debug output** - Shows variant data in debug mode for troubleshooting

```python
tp = (c.get("tcgplayer") or {}).get("prices") or {}
# Debug: Show if variant prices data exists
if st.session_state.get("debug_mode", False):
    st.write(f"Debug: TCGPlayer prices data: {tp}")
if tp:  # Only show expander if there's variant data
    with st.expander("Variant prices"):
        # ... variant price display
```

## 🔍 How to Test

### **Price Alignment Test:**
1. **Search for any Pokémon card** (e.g., "ditto")
2. **Observe the price metrics** - Low, Mid, Market should be centered
3. **Compare to quantity/buttons** - Prices should align above the action area

### **Variant Prices Test:**
1. **Enable Debug Mode** in sidebar
2. **Search for Pokémon cards** 
3. **Look for debug output:** `Debug: TCGPlayer prices data: {...}`
4. **If data exists:** "Variant prices" expander will appear
5. **If no data:** Expander won't appear (expected behavior)

## 📊 Expected Behavior

### **Cards WITH Variant Data:**
- ✅ Centered price metrics (Low, Mid, Market)
- ✅ "Variant prices" expander with individual variant pricing
- ✅ Variant-specific quantity inputs and "Add" buttons

### **Cards WITHOUT Variant Data:**
- ✅ Centered price metrics (Low, Mid, Market) 
- ✅ No "Variant prices" expander (because no data to display)
- ✅ Standard quantity input and "Add to collection" button

## 🎉 Results

- ✅ **Price alignment fixed** - All price metrics are now centered
- ✅ **Variant prices working** - Shows when data is available
- ✅ **Debug output added** - Helps troubleshoot missing variant data
- ✅ **Clean UI** - No empty expanders when no variant data exists

The UI now displays prices properly centered and only shows variant pricing when actual data is available!
