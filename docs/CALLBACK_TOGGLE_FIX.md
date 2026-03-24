# Callback Toggle Fix

## 🐛 Issue Identified

**Problem:** Toggle widgets were resetting to `True` when the app re-ran after searches. Users would disable sources, but as soon as they searched, the toggles would re-enable themselves.

## 🔍 Root Cause

Streamlit widgets with `key` parameters automatically manage session state, but there was a conflict between:
1. **Widget automatic state management**
2. **Manual session state initialization**
3. **App re-runs during searches**

When the app re-ran, the initialization code was interfering with the widget's state management.

## 🔧 Solution Applied

**Implemented callback-based state management:**

### **1. Created Callback Functions**
```python
def update_pokemon_toggle():
    """Callback to handle Pokémon toggle state change"""
    st.session_state.pokemon_enabled = st.session_state.pokemon_enabled_widget

def update_justtcg_toggle():
    """Callback to handle JustTCG toggle state change"""
    st.session_state.justtcg_enabled = st.session_state.justtcg_enabled_widget
```

### **2. Updated Toggle Widgets**
```python
# BEFORE (problematic)
pokemon_enabled = st.toggle("Enable Pokémon TCG API", value=st.session_state.pokemon_enabled, key="pokemon_enabled")

# AFTER (fixed with callback)
pokemon_enabled = st.toggle("Enable Pokémon TCG API", value=st.session_state.pokemon_enabled, key="pokemon_enabled_widget", on_change=update_pokemon_toggle)
```

### **3. Separated Widget Keys from State Keys**
- **Widget key:** `pokemon_enabled_widget` (for the widget itself)
- **State key:** `pokemon_enabled` (for the actual setting)
- **Callback:** Syncs widget changes to the state key

## ✅ How It Works

1. **Widget displays** using the value from `st.session_state.pokemon_enabled`
2. **User toggles** the widget → `pokemon_enabled_widget` changes
3. **Callback triggers** → copies widget value to `pokemon_enabled`
4. **Search function reads** from `pokemon_enabled` (not the widget key)
5. **App re-runs** → widget reads from stable `pokemon_enabled` value

## 🎯 Benefits

- ✅ **State persistence** across app re-runs
- ✅ **Clean separation** between widget and data state
- ✅ **No conflicts** between initialization and widget management
- ✅ **Predictable behavior** during searches

## 🧪 Testing

1. **Enable Debug Mode** to see real-time state changes
2. **Toggle JustTCG OFF** → Should show `False` in debug output
3. **Search for cards** → Should skip JustTCG and show `justtcg_enabled: False` in logs
4. **Toggle back ON** → Should work immediately

## 🎉 Status

**✅ COMPLETE** - Toggle states now persist correctly through searches and app re-runs!
