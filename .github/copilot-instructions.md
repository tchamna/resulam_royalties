# Resulam Royalties Dashboard - AI Coding Instructions

## Project Overview
A Dash-based analytics dashboard for Amazon KDP book sales and royalties data. Multi-page architecture with public (`/`) and internal (`/authors`) dashboards. Data flows from AWS S3 or local Google Drive sources.

## Architecture

### Core Components
- **Entry point**: [main.py](../main.py) - starts Flask server with Dash apps
- **Multi-page router**: [src/dashboard/multi_page.py](../src/dashboard/multi_page.py) - Flask blueprints mounting two Dash apps
- **Main dashboard**: [src/dashboard/app.py](../src/dashboard/app.py) - ~3000 lines, contains all Dash callbacks and layouts
- **Data processing**: [src/data/processor.py](../src/data/processor.py) - `DataLoader`, `DataCleaner`, `LanguageClassifier` classes
- **Configuration**: [src/config.py](../src/config.py) - paths, normalization mappings, exchange rates

### Data Flow
1. S3 sync at startup (`USE_S3_DATA=true`) OR local Google Drive paths
2. Excel sheets: `Combined Sales`, `eBook Royalty`, `Paperback Royalty`, `Hardcover Royalty`
3. CSV: Books database with metadata
4. Processing: normalization → language classification → author explosion → nickname mapping

## Critical Patterns

### Author/Title Normalization
Names have Unicode variations (accents, apostrophe types). Always use the mappings in `src/config.py`:
```python
AUTHOR_NORMALIZATION = {"Rodrigue": "Shck Tchamna", ...}
TITLE_NORMALIZATION = {"Conversation de base": "Conversations de base", ...}
```

### Book Nicknames (HARDCODED)
All 95+ titles map to short nicknames in [src/hardcoded_nicknames.py](../src/hardcoded_nicknames.py). When matching titles to nicknames, use fuzzy matching that normalizes Unicode:
```python
# Pattern from test_normalization.py - normalize quotes/apostrophes before comparison
text.replace('\u2019', "'")  # RIGHT SINGLE QUOTATION MARK
```

### Environment-Based Paths
```python
# src/config.py determines paths based on USE_S3_DATA env var
_USE_S3 = os.getenv('USE_S3_DATA', 'false').lower() == 'true'
# Local: G:\My Drive\Mbú'ŋwɑ̀'nì\RoyaltiesResulam\...
# EC2:   PROJECT_ROOT/data/...
```

## Development Commands

```powershell
# Activate virtual environment (Windows)
.\venv311\Scripts\Activate.ps1

# Run dashboard locally (uses Google Drive paths)
python main.py --debug

# Run with S3 data
$env:USE_S3_DATA="true"; python main.py

# Run specific debug/check scripts
python check_nicknames.py      # Verify title-to-nickname matching
python test_normalization.py   # Test Unicode normalization
```

## Deployment
- **EC2 deployment**: `.\deploy.ps1` handles SSH, systemd, nginx
- **Docker**: `docker-compose.yml` available
- **S3 webhook**: [src/api/webhooks.py](../src/api/webhooks.py) auto-syncs when files uploaded

## Key Conventions

1. **Visualization**: All charts use `plotly_white` template, defined in `VIZ_CONFIG`
2. **Language classification**: Determined by keywords in titles (see `LanguageClassifier.classify_language`)
3. **Currency conversion**: `USE_LIVE_RATES` toggles between API and hardcoded rates
4. **Net revenue**: 80% of royalties (`NET_REVENUE_PERCENTAGE = 0.8`)
5. **Excluded languages**: `['Bamileke', 'Africa']` filtered from visualizations

## File Structure Notes
- Root `test_*.py` and `check_*.py` files are standalone debugging scripts, not pytest
- [exports/](../exports/) contains processed CSV outputs
- [data/](../data/) stores S3-synced files and `exchange_rates_cache.json`
