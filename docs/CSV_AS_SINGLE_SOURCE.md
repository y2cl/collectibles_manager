# CSV as Single Source of Truth - Implementation Plan

## 🎯 Objective: Eliminate Redundant JSON Cache

### **✅ Current Situation Analysis:**

## **Data Redundancy Issue:**
- **JSON Cache:** `mtg_sets_cache.json` (basic fields, limited data)
- **CSV Data:** `mtgsets.csv` (complete fields, comprehensive data)
- **Problem:** Two separate files storing similar data → Redundancy, confusion, maintenance overhead

### **Current Data Flow:**
```
API Response → JSON Cache (limited fields) + CSV (complete fields) → UI
```

### **Proposed Data Flow:**
```
API Response → CSV (complete fields) → UI
```

---

## 🔧 Implementation Strategy

### **Phase 1: Create CSV Loading Function**
```python
def load_sets_from_csv(csv_file: str) -> List[Dict]:
    """Load sets from CSV file (replaces JSON cache loading)"""
    sets = []
    if not os.path.exists(csv_file):
        return sets
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert string representations back to proper types
                if row.get('card_count') and row['card_count'].isdigit():
                    row['card_count'] = int(row['card_count'])
                if row.get('digital') == 'True':
                    row['digital'] = True
                elif row.get('digital') == 'False':
                    row['digital'] = False
                if row.get('nonfoil_only') == 'True':
                    row['nonfoil_only'] = True
                elif row.get('nonfoil_only') == 'False':
                    row['nonfoil_only'] = False
                if row.get('foil_only') == 'True':
                    row['foil_only'] = True
                elif row.get('foil_only') == 'False':
                    row['foil_only'] = False
                
                # Parse JSON fields back to objects
                json_fields = ['related_uris', 'purchase_uris', 'booster_types']
                for field in json_fields:
                    if row.get(field) and row[field].startswith('['):
                        try:
                            row[field] = json.loads(row[field])
                        except:
                            row[field] = []
                
                sets.append(row)
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
    
    return sets
```

### **Phase 2: Update Cache Loading Logic**
```python
# Replace JSON cache loading with CSV loading
# OLD:
cached_sets = []
if os.path.exists(CACHE_FILES["mtg_sets"]):
    with open(CACHE_FILES["mtg_sets"], 'r') as f:
        cache_data = json.load(f)
        cached_sets = cache_data.get('sets', [])

# NEW:
csv_file = CACHE_FILES["mtg_sets"].replace('.json', '.csv')
cached_sets = load_sets_from_csv(csv_file)
```

### **Phase 3: Update Clear Cache Logic**
```python
# Update clear cache to work with CSV
# OLD:
clear_cache_function=lambda f: os.remove(f) if os.path.exists(f) else None

# NEW:
def clear_csv_cache(csv_file):
    if os.path.exists(csv_file):
        os.remove(csv_file)
    # Also remove corresponding JSON if it exists
    json_file = csv_file.replace('.csv', '.json')
    if os.path.exists(json_file):
        os.remove(json_file)

clear_cache_function=lambda f: clear_csv_cache(f.replace('.json', '.csv'))
```

### **Phase 4: Update Constants**
```python
# Update CACHE_FILES to point to CSV
CACHE_FILES = {
    "pokemon_sets": "pokemon_sets_cache.json",  # Keep Pokemon as JSON for now
    "mtg_sets": "mtgsets.csv"  # Change to CSV
}
```

---

## 📋 Implementation Steps

### **Step 1: Create CSV Loading Function**
- Add `load_sets_from_csv()` function to handle CSV parsing
- Handle type conversions (strings back to proper types)
- Parse JSON fields back to objects

### **Step 2: Update MTG Sets Loading**
- Replace JSON cache loading with CSV loading
- Update file path references
- Test data integrity

### **Step 3: Update Clear Cache Logic**
- Modify clear cache to handle CSV files
- Clean up any remaining JSON files
- Update error messages

### **Step 4: Update Constants and References**
- Update CACHE_FILES for MTG to point to CSV
- Update any other references to mtg_sets_cache.json
- Ensure consistency across the codebase

### **Step 5: Testing and Validation**
- Test CSV loading performance
- Verify data completeness
- Test clear cache functionality
- Validate UI display

---

## 🎯 Benefits of This Change

### **✅ Advantages:**
1. **Single Source of Truth:** No more data duplication
2. **Complete Data Access:** UI has access to all 30+ fields
3. **Simplified Maintenance:** Only one file to manage
4. **Reduced Storage:** No duplicate data storage
5. **Consistent Updates:** CSV updates are immediately reflected
6. **Better Performance:** CSV loading can be optimized
7. **Data Integrity:** No risk of JSON/CSV mismatch

### **📊 Storage Comparison:**
```
BEFORE:
├── mtg_sets_cache.json    (~500KB, basic fields)
└── mtgsets.csv           (~2MB, complete fields)
Total: ~2.5MB

AFTER:
└── mtgsets.csv           (~2MB, complete fields)
Total: ~2MB
Storage Savings: ~20%
```

### **🔄 Maintenance Comparison:**
```
BEFORE:
- Update API → Update JSON → Update CSV → Sync Issues
- Clear Cache → Clear JSON only (CSV remains)
- Data Mismatch → JSON vs CSV inconsistencies

AFTER:
- Update API → Update CSV only
- Clear Cache → Clear CSV only
- Single Source → No sync issues
```

---

## ⚠️ Considerations and Risks

### **Potential Issues:**
1. **Performance:** CSV loading might be slower than JSON
2. **Type Conversion:** Need careful type parsing
3. **Backward Compatibility:** Ensure no breaking changes
4. **Pokemon Sets:** Keep Pokemon as JSON for now (different structure)

### **Mitigation Strategies:**
1. **Performance:** Implement efficient CSV parsing with type hints
2. **Type Conversion:** Create robust type conversion functions
3. **Backward Compatibility:** Maintain existing UI interface
4. **Gradual Migration:** Start with MTG, evaluate Pokemon later

---

## 🚀 Implementation Priority

### **High Priority:**
1. Create `load_sets_from_csv()` function
2. Update MTG sets loading logic
3. Test basic functionality

### **Medium Priority:**
4. Update clear cache logic
5. Update constants and references
6. Comprehensive testing

### **Low Priority:**
7. Performance optimization
8. Pokemon sets migration (future)
9. Cleanup legacy code

---

## 🎉 Expected Outcome

**After implementation:**

- **✅ Single Data Source:** CSV only for MTG sets
- **✅ Complete Data Access:** All 30+ fields available in UI
- **✅ Simplified Architecture:** No more data duplication
- **✅ Better Maintainability:** One file to manage
- **✅ Storage Efficiency:** ~20% storage reduction
- **✅ Data Consistency:** No sync issues between files

**This change will significantly simplify the codebase while providing access to richer data!** 🚀
