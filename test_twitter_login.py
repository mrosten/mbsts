"""
Test Twitter login with Selenium
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

print("=== Testing Twitter Login ===\n")

# Setup Chrome
print("1. Setting up Chrome...")
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

driver = webdriver.Chrome(options=chrome_options)
print("✅ Chrome ready\n")

try:
    print("2. Navigating to Twitter login...")
    driver.get("https://twitter.com/i/flow/login")
    time.sleep(3)
    
    print("3. Entering username...")
    username_input = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']"))
    )
    username_input.send_keys("mosherosten")
    username_input.send_keys(Keys.RETURN)
    time.sleep(3)
    
    # Check for email verification
    print("4. Checking for verification step...")
    try:
        verification_input = driver.find_element(By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']")
        print("   Email verification requested!")
        verification_input.send_keys("mosherosten@gmail.com")
        verification_input.send_keys(Keys.RETURN)
        time.sleep(2)
    except:
        print("   No verification needed")
    
    print("5. Entering password...")
    password_input = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
    )
    password_input.send_keys("Myrost6045!!mmm")
    password_input.send_keys(Keys.RETURN)
    
    print("6. Waiting for login to complete...")
    time.sleep(5)
    
    # Check if we're logged in by looking for the home timeline
    print("7. Verifying login...")
    current_url = driver.current_url
    print(f"   Current URL: {current_url}")
    
    if "home" in current_url or "timeline" in current_url:
        print("✅ LOGIN SUCCESSFUL!\n")
        
        # Now try to navigate to Elon's profile
        print("8. Navigating to @elonmusk profile...")
        driver.get("https://twitter.com/elonmusk")
        time.sleep(5)
        
        # Look for tweets
        print("9. Looking for tweets...")
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
        print(f"✅ Found {len(tweet_elements)} tweets!")
        
        if tweet_elements:
            print("\n10. Sample tweet content:")
            for i, elem in enumerate(tweet_elements[:2]):
                try:
                    text_elem = elem.find_element(By.CSS_SELECTOR, "[data-testid='tweetText']")
                    print(f"\n   Tweet {i+1}: {text_elem.text[:100]}...")
                except:
                    pass
    else:
        print("❌ Login may have failed - unexpected URL")
        # Save page source for debugging
        with open("login_result.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("   Saved page source to login_result.html")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
    print("\n✅ Test complete!")
