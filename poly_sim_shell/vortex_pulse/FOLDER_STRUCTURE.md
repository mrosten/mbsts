# Vortex Pulse Folder Organization

## Main Program Files (root directory)
- **app.py** - Main application with UI and core logic
- **broker.py** - Trading broker interface (SIM/LIVE)
- **config.py** - Configuration settings
- **ftp_manager.py** - FTP upload management
- **intel_scanners.py** - Intelligence scanner implementations
- **market.py** - Market data fetching and processing
- **pulse_settings.json** - User settings persistence
- **risk.py** - Risk management and bet sizing
- **scanners.py** - Technical analysis scanners
- **trade_engine.py** - Trade execution engine
- **ui_modals.py** - UI modal dialogs
- **ui_modals_intel.py** - Intelligence scanner modals
- **README.md** - Main documentation
- **__init__.py** - Python package initialization

## Subfolders

### dev_tools/
Development and debugging utilities:
- check_p2b_sequence.py - Price-to-beat sequence verification
- check_timing.py - Timing analysis tools
- debug_market_extract.py - Market data debugging
- debug_p2b.py - Price-to-beat debugging
- dump_market.py - Market data dumping
- find_active.py - Find active markets
- find_resolved.py - Find resolved markets
- fix_trend.py - Trend fixing utilities
- poll_market.py - Market polling tools
- price_to_beat_extractor.py - Price extraction tools
- repro_p2b.py - Reproduce P2B issues
- verify_caching.py - Cache verification
- verify_history.py - History verification
- verify_market.py - Market verification

### docs/
Documentation files:
- HTML_Price_to_Beat_Logic.md - Technical documentation
- README_v5.md - Version 5 documentation
- docs.html - HTML documentation

### scripts/
Installation and alternative run scripts:
- install_pillow.py - Pillow dependency installer
- install_vortex_deps.ps1 - Windows dependency script
- install_vortex_deps.sh - Linux/Mac dependency script
- main.py - Alternative main entry point
- run_pulse.py - Alternative run script

### temp/
Temporary files and cache:
- cache_output*.txt - Cache output files
- debug_output*.txt - Debug output files
- failed_market.json - Failed market data
- latest_market.json - Latest market data
- pulse_log_*.html - Old HTML logs
- shutdown_hits.txt - Shutdown tracking
- temp_queries.txt - Temporary queries
- threading_hits.txt - Threading debug info
- to_thread_hits.txt - Thread conversion debug

### lg/ & lg2/
Log directories (empty, ready for session logs)

### fff/
Additional folder (empty)

### __pycache__/
Python bytecode cache (standard Python folder)
