# TCG Price Tracker - Project Structure

## 📁 **Folder Organization**

### **📂 Root Directory: `/tcgpricetracker/`**
```
tcgpricetracker/
├── 📄 Main Application Files
│   ├── tcgpricetracker.py          # Main Streamlit app
│   ├── ui_handlers.py              # UI rendering functions
│   ├── constants.py                # App constants and paths
│   ├── fallback_manager.py         # Fallback data management
│   └── .streamlit/                 # Streamlit configuration
│       └── secrets.toml            # API keys and secrets
│
├── 📁 docs/                        # Documentation
│   ├── PROJECT_STRUCTURE.md        # This file
│   ├── CSV_FIELDS_UPDATE_COMPLETE.md
│   ├── SMART_UPDATE_COMPLETE.md
│   └── [all other .md files]
│
├── 📁 utility/                     # Utility scripts
│   ├── enhanced_mtg_sets.py        # MTG sets enhancement tools
│   ├── fix_mtg_csv.py              # CSV cleaning and repair
│   ├── update_mtg_csv_fields.py    # CSV field expansion
│   └── old/                        # Archived utilities
│       ├── README.md               # Archive documentation
│       ├── add_game_type.py        # Deprecated game type script
│       ├── add_scryfall_link.py    # Deprecated link script
│       ├── mtg_sets_cache.csv      # Old cached data
│       └── mtg_sets_cache.json     # Old cached data
│
├── 📁 logs/                        # Log files
│   └── pokemon_search.log          # Pokemon API search logs
│
├── 📁 fallback_data/              # Local data cache
│   ├── MTG/
│   │   ├── mtgsets.csv            # MTG sets database
│   │   ├── SetImages/             # MTG set icons
│   │   └── CardImages/            # MTG card images
│   └── Pokemon/
│       ├── pokemonsets.csv        # Pokemon sets database
│       ├── SetImages/             # Pokemon set icons
│       └── CardImages/            # Pokemon card images
│
├── 📄 toggle_settings.json        # App toggle settings
├── 📁 __pycache__/                 # Python cache files
└── 📁 .venv/                      # Virtual environment
```

---

## 🎯 **File Categories**

### **📄 Core Application**
- **`tcgpricetracker.py`** - Main Streamlit application
- **`ui_handlers.py`** - UI components and page rendering
- **`constants.py`** - Global constants and configuration
- **`fallback_manager.py`** - Data caching and storage management

### **📁 Documentation (`docs/`)**
All `.md` files documenting:
- Feature implementations
- Bug fixes and solutions
- Technical specifications
- Update summaries
- Project architecture

### **🔧 Utility Scripts (`utility/`)**
All `.py` utility scripts for:
- Data migration and repair
- CSV processing and cleaning
- Field expansion and updates
- Maintenance tasks

### **�️ Archived Utilities (`utility/old/`)**
Deprecated scripts kept for:
- Historical reference
- Development evolution tracking
- Logic snippets for future reference
- **DO NOT USE** - obsolete code

### **📝 Log Files (`logs/`)**
Application logs for:
- API request debugging
- Error tracking
- Performance monitoring
- Search activity logs

### **�💾 Data Storage (`fallback_data/`)**
Local cache for:
- MTG and Pokemon sets (CSV files)
- Card and set images
- Backup files
- Temporary data

---

## 📋 **File Naming Conventions**

### **📄 Python Files**
- **Core:** `lowercase_with_underscores.py`
- **Utility:** `descriptive_name.py` (in `utility/` folder)
- **Main:** `tcgpricetracker.py`

### **📁 Documentation**
- **Format:** `DESCRIPTIVE_NAME.md`
- **Style:** `UPPERCASE_WITH_UNDERSCORES`
- **Location:** `docs/` folder

### **💾 Data Files**
- **CSV:** `lowercase.csv` (e.g., `mtgsets.csv`)
- **Images:** `{id}_{type}.{ext}` (e.g., `lea_icon.svg`)
- **Backups:** `{filename}_backup_{timestamp}.csv`

---

## 🔄 **Development Workflow**

### **✅ Creating New Files:**
1. **Documentation:** → `docs/NEW_FEATURE.md`
2. **Utility Scripts:** → `utility/new_tool.py`
3. **Core Features:** → Root directory (if main app logic)

### **✅ File References:**
- **Relative imports:** Use `from utility.tool import function`
- **Documentation links:** Reference as `docs/FILENAME.md`
- **Data paths:** Use `constants.py` for all data paths

### **✅ Maintenance:**
- **Clean docs:** Keep documentation current with code changes
- **Utility updates:** Update related docs when modifying tools
- **Backups:** Create backups before major data changes

---

## 🎯 **Best Practices**

### **📁 Organization:**
- **Separation:** Keep core app separate from utilities
- **Documentation:** Document all significant changes
- **Naming:** Use consistent, descriptive naming

### **🔧 Utilities:**
- **Self-contained:** Each utility should work independently
- **Documented:** Include usage instructions in docstrings
- **Tested:** Test utilities on sample data before production

### **📄 Documentation:**
- **Current:** Keep docs in sync with code
- **Comprehensive:** Include before/after examples
- **Searchable:** Use consistent naming for easy reference

---

## 📞 **Quick Reference**

### **🔧 Common Tasks:**
- **Add utility:** → `utility/new_tool.py`
- **Document feature:** → `docs/FEATURE.md`
- **Fix CSV:** → `python utility/fix_mtg_csv.py`
- **Update fields:** → `python utility/update_mtg_csv_fields.py`

### **📁 Important Paths:**
- **Main app:** `tcgpricetracker.py`
- **Constants:** `constants.py`
- **Data:** `fallback_data/`
- **Docs:** `docs/`
- **Utilities:** `utility/`

---

**This structure ensures organized, maintainable, and scalable development!** 🚀
