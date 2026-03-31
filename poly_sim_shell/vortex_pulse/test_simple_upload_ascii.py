#!/usr/bin/env python3
"""
Simple Upload Test - ASCII only
Tests basic FTP upload functionality without Unicode issues.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_simple_upload():
    print("Testing simple FTP upload...")
    
    try:
        from ftp_manager import FTPManager
        
        # Create a simple test file (ASCII only)
        test_content = """<!DOCTYPE html>
<html>
<head><title>Test Upload</title></head>
<body>
    <h1>Upload Test Successful</h1>
    <p>Time: {}</p>
    <p>This confirms FTP uploads are working.</p>
</body>
</html>""".format(time.strftime('%Y-%m-%d %H:%M:%S'))
        
        test_file = "test_upload.html"
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Upload test
        ftp_manager = FTPManager()
        ftp_manager.set_session("test_upload")
        ftp_manager.upload_html_log(test_file)
        
        print("Test upload completed!")
        print("Check: http://myfavoritemalshin.space/test_upload/verification.html")
        
        # Clean up
        os.remove(test_file)
        
        return 0
        
    except Exception as e:
        print(f"Test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_simple_upload())
