import asyncio
from twikit import Client

async def test_login():
    print("Starting login test...")
    client = Client('en-US')
    
    try:
        print("Attempting to login...")
        await client.login(
            auth_info_1='mosherosten',
            auth_info_2='mosherosten@gmail.com',
            password='Myrost6045!!mmm'
        )
        print("Login successful!")
        
        print("Fetching Elon Musk's profile...")
        user = await client.get_user_by_screen_name('elonmusk')
        print(f"Found user: {user.name}")
        
        print("Fetching tweets...")
        tweets = await user.get_tweets('Tweets', count=5)
        
        print(f"\\nFetched {len(tweets)} tweets:\\n")
        for i, tweet in enumerate(tweets, 1):
            print(f"{i}. {tweet.text[:100]}...")
            print(f"   Created: {tweet.created_at}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_login())
