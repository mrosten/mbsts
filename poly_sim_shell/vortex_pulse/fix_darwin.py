#!/usr/bin/env python3
"""
Fix Darwin Algorithm Configuration
Sets Darwin to V2 mode and updates algorithm with improved logic.
"""

import os
import sys
from pathlib import Path

def main():
    print("🔧 Fixing Darwin Algorithm Configuration...")
    
    # 1. Set Darwin to V2 Experimenter mode
    env_file = Path(__file__).parent / ".env"
    
    if env_file.exists():
        content = env_file.read_text()
        lines = content.split('\n')
        
        # Update or add DARWIN_MODE
        updated_lines = []
        darwin_updated = False
        
        for line in lines:
            if line.startswith('DARWIN_MODE='):
                updated_lines.append('DARWIN_MODE=V2_EXPERIMENTER')
                darwin_updated = True
                print("✅ Updated DARWIN_MODE to V2_EXPERIMENTER")
            else:
                updated_lines.append(line)
        
        if not darwin_updated:
            updated_lines.append('DARWIN_MODE=V2_EXPERIMENTER')
            print("✅ Added DARWIN_MODE=V2_EXPERIMENTER")
        
        env_file.write_text('\n'.join(updated_lines))
        print(f"📝 Updated {env_file}")
    
    # 2. Replace current algorithm with improved version
    current_algo = Path(__file__).parent / "darwin" / "current_algo.py"
    improved_algo = Path(__file__).parent / "darwin" / "current_algo_improved.py"
    
    if improved_algo.exists():
        improved_code = improved_algo.read_text()
        current_algo.write_text(improved_code)
        print("✅ Updated algorithm with improved logic")
        print("🚀 Darwin is now ready to trade in V2 mode!")
    else:
        print("❌ Improved algorithm file not found")
        return 1
    
    print("\n📋 Summary of fixes:")
    print("  • Fixed: Darwin was in V1 Observer mode (no trading)")
    print("  • Fixed: Algorithm was too restrictive (needed exactly 1 VolSnap trigger)")
    print("  • Fixed: Wrong trend format checking (was looking for 'S-'/W-', now uses 'UP'/'DOWN')")
    print("  • Fixed: Extreme thresholds (2% moves, ±20 odds) reduced to reasonable levels")
    print("  • Added: Support for multiple scanner confirmations")
    print("\n⚠️  Restart the application for changes to take effect")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
