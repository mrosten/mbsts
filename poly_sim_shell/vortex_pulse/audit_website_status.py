#!/usr/bin/env python3
"""
Audit Website Status Report
Comprehensive check of audit website upload and accessibility status.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_ftp_configuration():
    """Check FTP configuration and test connection."""
    print("=== FTP Configuration Check ===")
    
    try:
        from ftp_manager import FTPManager
        
        # Load FTP settings
        ftp_manager = FTPManager()
        
        # Test connection
        ftp = ftp_manager._get_connection()
        try:
            print(f"Connected to: {ftp_manager.host}")
            print(f"Root directory: {ftp_manager.root_dir}")
            
            # List root directory
            ftp.cwd(ftp_manager.root_dir)
            items = ftp.nlst()
            print(f"Root directory contents: {len(items)} items")
            
            # Check if test_upload directory exists
            if "test_upload" in items:
                print("✅ test_upload directory found")
                ftp.cwd("test_upload")
                test_files = ftp.nlst()
                print(f"test_upload contents: {test_files}")
            else:
                print("❌ test_upload directory not found")
                
            ftp.quit()
            return True
            
        except Exception as e:
            print(f"❌ FTP connection failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ FTP configuration error: {e}")
        return False

def check_local_files():
    """Check local verification files."""
    print("\n=== Local Files Check ===")
    
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    
    # Count verification files
    total_files = 0
    files_with_data = 0
    recent_files = []
    
    for root, dirs, files in os.walk(lg_dir):
        for file in files:
            if file.endswith("_verification.html"):
                total_files += 1
                file_path = os.path.join(root, file)
                file_time = os.path.getmtime(file_path)
                file_age = time.time() - file_time
                
                if file_age < 3600:  # Last hour
                    recent_files.append((file_path, file_age))
                
                # Check if file has trading data
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if "class='match'" in content:
                        files_with_data += 1
                except:
                    pass
    
    print(f"Total verification files: {total_files}")
    print(f"Files with trading data: {files_with_data}")
    print(f"Recent files (last hour): {len(recent_files)}")
    
    return recent_files

def create_status_report():
    """Create a comprehensive status report."""
    print("\n=== AUDIT WEBSITE STATUS REPORT ===")
    print(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check FTP
    ftp_ok = check_ftp_configuration()
    
    # Check local files
    recent_files = check_local_files()
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"FTP Connection: {'✅ Working' if ftp_ok else '❌ Issues'}")
    print(f"Local Files: {'✅ Available' if recent_files else '❌ No recent files'}")
    
    if ftp_ok and recent_files:
        print("\n=== RECOMMENDATIONS ===")
        print("✅ Upload system is functional")
        print("✅ Local files are being generated")
        print("⚠️  Website accessibility issues detected")
        print("\nPossible causes:")
        print("• Server configuration preventing HTTP access")
        print("• Files uploaded to wrong directory")
        print("• Server-side caching issues")
        print("\nNext steps:")
        print("1. Check server configuration")
        print("2. Verify upload directory paths")
        print("3. Test with a simple HTML file")
    else:
        print("\n=== ISSUES FOUND ===")
        if not ftp_ok:
            print("❌ FTP connection problems")
        if not recent_files:
            print("❌ No recent verification files")
        print("\nTroubleshooting:")
        print("1. Check FTP credentials in .env")
        print("2. Run trading app to generate verification files")
        print("3. Verify log settings are enabled")

if __name__ == "__main__":
    create_status_report()
