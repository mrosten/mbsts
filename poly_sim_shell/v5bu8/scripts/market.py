import time
import requests
import json
import re
import asyncio
import threading
import websockets
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Handle imports for both package and direct execution
try:
    from .config import TradingConfig
except ImportError:
    # Running directly from vortex_pulse directory
    from config import TradingConfig

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    up = sum(d for d in deltas[:period] if d > 0) / period
    down = sum(-d for d in deltas[:period] if d < 0) / period
    if down == 0: return 100
    for i in range(period, len(deltas)):
        d = deltas[i]; g = d if d > 0 else 0; l = -d if d < 0 else 0
        up = (up * (period - 1) + g) / period; down = (down * (period - 1) + l) / period
    if down == 0: return 100
    return 100 - (100 / (1 + up/down))

def calculate_bb(prices, period=20):
    if len(prices) < period: return 0, 0, 0
    slice_ = prices[-period:]; sma = sum(slice_) / period
    std = (sum((x - sma) ** 2 for x in slice_) / period) ** 0.5
    return sma + (std*2), sma, sma - (std*2)

def calculate_atr(highs, lows, closes, period=14):
    if len(highs) < period + 1: return 0
    tr_list = []
    for i in range(1, len(highs)):
        h, l, pc = highs[i], lows[i], closes[i-1]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    # Simple Moving Average of TR
    return sum(tr_list[-period:]) / period

class MarketDataManager:
    def __init__(self, config=None, logger_func=None):
        self.config = config if config else TradingConfig()
        self.logger = logger_func if logger_func else print
        
        # Initialize requests session with retries for GCP stability
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        if self.config.HTTP_PROXY:
            self.session.proxies = {
                "http": self.config.HTTP_PROXY,
                "https": self.config.HTTP_PROXY
            }
        self.market_data = {
            "btc_price": 0, "btc_open": 0, "start_ts": 0, 
            "up_p": 0.5, "down_p": 0.5, "up_price": 0.5, "down_price": 0.5,
            "up_bid": 0.5, "down_bid": 0.5, "up_ask": 0.51, "down_ask": 0.51,
            "up_id": None, "down_id": None,
            "sling_signal": "OFF", "cobra_signal": "OFF", "flag_signal": "OFF",
            "master_score": 0, "master_status": "NEUTRAL", "active_scanners": 0,
            "trend_4h": "NEUTRAL", "trend_1h": "NEUTRAL",
            "rsi_1m": 50.0, "atr_5m": 0.0, "odds_score": 0, "btc_dyn_rng": 0,
            "vol_up": 0, "vol_dn": 0
        }
        self.chainlink_contract = None
        self.price_history = []
        self.trend_4h = "NEUTRAL"
        self.trend_1h = "NEUTRAL"  # Add 1-hour trend
        self.atr_5m = 0.0
        self.last_4h_update = 0
        self.last_1h_update = 0  # Add 1h update timer
        self.first_update = True
        
        # Live WebSocket Price variables
        self.live_price = 0.0
        self.last_ws_update = 0
        self.ws_thread = threading.Thread(target=self._start_ws_thread, daemon=True)
        self.ws_thread.start()
        
        # Connection status tracking to suppress log spam
        self.connection_lost = False
        self.just_reconnected = False
        
        # Price to beat caching to prevent repeated webpage scraping
        self._p2b_cache = {}  # {slug: {"t30_price": float, "t330_price": float, "timestamp": float}}
        self._scraped_p2b_cache = {} # {slug: float}
        self._scraped_p2b_fail_ts = {} # {slug: float} (Negative cache for failures)
        
        self.app_active = True
        
    def _start_ws_thread(self):
        """Initializes a new event loop for the background WebSocket connection."""
        time.sleep(1) # Allow Textual UI time to mount before processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._kraken_ws_loop())

    async def _kraken_ws_loop(self):
        """Maintains a continuous WebSocket connection to Kraken for real-time BTC/USD pricing."""
        uri = "wss://ws.kraken.com/"
        while self.app_active:
            try:
                self.log("[cyan]Connecting to Kraken WebSocket...[/]")
                async with websockets.connect(uri) as ws:
                    self.ws_conn = ws # Store for manual closure
                    self.log("[green]Kraken WebSocket Connected.[/]")
                    subscribe_message = {
                        "event": "subscribe",
                        "pair": ["XBT/USD"],
                        "subscription": {"name": "ticker"}
                    }
                    await ws.send(json.dumps(subscribe_message))

                    while self.app_active:
                        try:
                            # Use wait_for to ensure we check self.app_active even if no messages arrive
                            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            data = json.loads(response)
                            
                            if isinstance(data, list) and len(data) > 1 and 'ticker' in data:
                                ticker_payload = data[1]
                                if 'c' in ticker_payload:
                                    self.live_price = float(ticker_payload['c'][0])
                                    self.last_ws_update = time.time()
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            if self.app_active:
                                self.log(f"[yellow]Kraken WS Loop Error: {e}[/]")
                                break
                            else: return
            except Exception as e:
                if self.app_active:
                    self.log(f"[yellow]Kraken WS Disconnected: {e}. Reconnecting in 3s...[/]")
                    await asyncio.sleep(3)

    def stop(self):
        """Signals background threads and connections to terminate."""
        self.app_active = False
        self.logger("[dim]MarketDataManager stopping background threads...[/]")
        try:
            if hasattr(self, "session") and self.session:
                self.session.close()
                self.logger("[dim]Network session closed.[/]")
        except Exception as e:
            self.logger(f"[dim]Error closing network session: {e}[/]")
        
        if hasattr(self, "ws_conn") and self.ws_conn:
            # WebSocket stop logic - loop checks self.app_active
            pass

    def log(self, msg, is_connection_error=False, level="INFO"):
        try:
            if is_connection_error:
                if self.connection_lost:
                    return # Suppress redundant connection error logs
                self.connection_lost = True
            elif self.connection_lost:
                # If we get here with a successful call (non-connection error), reset status
                self.log("[green]INTERNET CONNECTION RESTORED[/]")
                self.connection_lost = False
                self.just_reconnected = True

            if self.logger:
                # Check if the logger supports a level argument
                try:
                    self.logger(msg, level=level)
                except TypeError:
                    self.logger(msg)
        except Exception:
            pass # Failsafe if the UI thread is not ready to receive logs

    def update_4h_trend(self):
        if (time.time() - self.last_4h_update) < 900: return
        try:
            r = self.session.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"4h","limit":10}, timeout=self.config.REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            closes = [float(x[4]) for x in data]
            short = sum(closes[-3:]) / 3; long_ = sum(closes) / len(closes)
            
            # Calculate trend strength percentage
            trend_pct = ((short / long_) - 1) * 100
            
            # Determine trend direction and strength
            if trend_pct >= 0.5:  # Strong uptrend (0.5%+)
                self.trend_4h = "S-UP"  # Strong UP
            elif trend_pct >= 0.2:  # Medium uptrend (0.2%+)
                self.trend_4h = "M-UP"  # Medium UP
            elif trend_pct >= 0.05:  # Weak uptrend (0.05%+)
                self.trend_4h = "W-UP"  # Weak UP
            elif trend_pct <= -0.5:  # Strong downtrend (-0.5%+)
                self.trend_4h = "S-DOWN"  # Strong DOWN
            elif trend_pct <= -0.2:  # Medium downtrend (-0.2%+)
                self.trend_4h = "M-DOWN"  # Medium DOWN
            elif trend_pct <= -0.05:  # Weak downtrend (-0.05%+)
                self.trend_4h = "W-DOWN"  # Weak DOWN
            else:
                self.trend_4h = "NEUTRAL"
                
            self.last_4h_update = time.time()
        except requests.RequestException as e:
            self.log(f"[yellow]Warn: 4H Trend Update Failed: {e}[/]", is_connection_error=True)
        except Exception as e:
            self.log(f"[red]Error: 4H Trend Calc Error: {e}[/]")

    def update_1h_trend(self):
        """Calculate 1-hour trend for more responsive 5-minute market analysis."""
        if (time.time() - getattr(self, 'last_1h_update', 0)) < 900: return
        try:
            r = self.session.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"1h","limit":12}, timeout=self.config.REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            closes = [float(x[4]) for x in data]
            short = sum(closes[-3:]) / 3; long_ = sum(closes) / len(closes)
            
            # Calculate trend strength percentage
            trend_pct = ((short / long_) - 1) * 100
            
            # Determine trend direction and strength
            if trend_pct >= 0.3:  # Strong uptrend (0.3%+)
                self.trend_1h = "S-UP"  # Strong UP
            elif trend_pct >= 0.15:  # Medium uptrend (0.15%+)
                self.trend_1h = "M-UP"  # Medium UP
            elif trend_pct >= 0.05:  # Weak uptrend (0.05%+)
                self.trend_1h = "W-UP"  # Weak UP
            elif trend_pct <= -0.3:  # Strong downtrend (-0.3%+)
                self.trend_1h = "S-DOWN"  # Strong DOWN
            elif trend_pct <= -0.15:  # Medium downtrend (-0.15%+)
                self.trend_1h = "M-DOWN"  # Medium DOWN
            elif trend_pct <= -0.05:  # Weak downtrend (-0.05%+)
                self.trend_1h = "W-DOWN"  # Weak DOWN
            else:
                self.trend_1h = "NEUTRAL"
                
            self.last_1h_update = time.time()
        except requests.RequestException as e:
            self.log(f"[yellow]Warn: 1H Trend Update Failed: {e}[/]", is_connection_error=True)
        except Exception as e:
            self.log(f"[red]Error: 1H Trend Calc Error: {e}[/]")

    def update_atr(self):
        """Fetches 1m klines and updates the 5-period ATR (Average True Range)."""
        try:
            closes, lows, highs, _ = self.fetch_candles_60m()
            if highs and lows and closes:
                self.atr_5m = calculate_atr(highs, lows, closes, period=5)
        except Exception as e:
            self.log(f"[yellow]Warn: ATR Update Failed: {e}[/]")

    def fetch_candles_60m(self):
        try:
            r = self.session.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"1m","limit":200}, timeout=self.config.REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return [float(x[4]) for x in data], [float(x[3]) for x in data], [float(x[2]) for x in data], data
        except Exception as e:
            self.log(f"[yellow]Warn: candles Fetch Failed: {e}[/]", is_connection_error=True)
            return [], [], [], []

    def fetch_current_price(self):
        last_known = self.market_data.get("btc_price", 0)

        def _plausible(price):
            """Returns True if price is reasonable relative to last known. Always True if no baseline."""
            if last_known <= 0 or price <= 0:
                return price > 0
            return abs(price - last_known) / last_known < 0.05 # Reject if >5% from last known

        # 1. Primary: Live Kraken WebSocket Price (Must be fresh < 5 seconds)
        if self.live_price > 0 and (time.time() - self.last_ws_update) < 5:
            if _plausible(self.live_price):
                return self.live_price
            else:
                pass  # BTC Sanity: WS price rejected silently

        # 2. Secondary: Chainlink Oracle Backup
        if self.chainlink_contract:
            try:
                raw = self.chainlink_contract.functions.latestAnswer().call()
                price = float(raw) / 10**8
                if _plausible(price):
                    return price
                else:
                    pass  # BTC Sanity: Chainlink price rejected silently
            except: pass

        # 3. Tertiary: Binance REST Fallback
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=3).json()
            price = float(r['price'])
            if _plausible(price):
                return price
            else:
                pass  # BTC Sanity: Binance price rejected silently
        except Exception: pass

        # 4. Last resort: return last known price (stale but safe)
        # BTC Sanity: all sources failed — fall back silently to last known price
        return last_known if last_known > 0 else 0

    def fetch_oracle_price(self):
        if self.chainlink_contract:
            try:
                price = self.chainlink_contract.functions.latestAnswer().call()
                return float(price) / 10**8
            except: pass
        return 0.0

    def reset_history(self):
        self.price_history = []

    def update_history(self, curr_price, start_ts, elapsed):
        if self.first_update and not self.price_history and elapsed > 5:
            self.first_update = False
            try:
                r = requests.get("https://api.kraken.com/0/public/OHLC", 
                                 params={"pair":"XBTUSD", "interval":1, "since":start_ts-60}, 
                                 timeout=3).json()
                
                if 'result' in r and 'XXBTZUSD' in r['result']:
                    candles = r['result']['XXBTZUSD']
                    target_candle = next((c for c in candles if int(c[0]) == start_ts), None)
                    
                    if target_candle:
                        open_p = float(target_candle[1]) 
                        self.price_history.append({'timestamp': start_ts, 'elapsed': 0, 'price': open_p})
                        self.log(f"[cyan]Fixed Mid-Window Start: Found Kraken Open @ ${open_p:,.2f}[/]", level="SYS")
            except:
                pass
        
        self.first_update = False
        self.price_history.append({'timestamp': time.time(), 'elapsed': elapsed, 'price': curr_price})
        return self.price_history[0]['price'] if self.price_history else curr_price

    def store_html_price_to_beat(self, slug, window_elapsed):
        """
        Store HTML price to beat at T+30 for later comparison.
        This is the more accurate price that gets documented.
        """
        if window_elapsed >= 30 and window_elapsed <= 35:
            cached = self._p2b_cache.get(slug, {})
            if cached.get("t30_price") is None:  # Only store once
                html_p2b = self._extract_price_to_beat_from_web(slug)
                if html_p2b:
                    self._p2b_cache[slug] = {
                        "t30_price": html_p2b,
                        "t330_price": None,
                        "timestamp": time.time()
                    }
                    self.log(f"[cyan]HTML PTB stored: ${html_p2b:,.2f}[/]")
                    return html_p2b
        return None

    def compare_html_price_to_beat(self, slug, window_elapsed):
        """
        Compare HTML price to beat at T+330 with T+30 value.
        If direction changed, log and return the change.
        """
        if window_elapsed >= 330 and window_elapsed <= 335:
            cached = self._p2b_cache.get(slug, {})
            t30_price = cached.get("t30_price")
            
            if t30_price and cached.get("t330_price") is None:
                # Get current HTML price to beat for comparison
                current_html_p2b = self._extract_price_to_beat_from_web(slug)
                if current_html_p2b:
                    self._p2b_cache[slug]["t330_price"] = current_html_p2b
                    
                    if current_html_p2b != t30_price:
                        self.log(f"[red]⚠️ HTML PTB CHANGED: ${t30_price:,.2f} → ${current_html_p2b:,.2f}[/]")
                        return {
                            "changed": True,
                            "t30_price": t30_price,
                            "t330_price": current_html_p2b,
                            "slug": slug
                        }
                        
            return None

    def _extract_price_to_beat_from_web(self, slug):
        """
        Extract price to beat from Polymarket webpage when API doesn't provide it.
        Uses both regex and __NEXT_DATA__ JSON parsing for robustness.
        """
        try:
            # Use /event/ for 5m windows as /market/ can be stale or redirect
            market_url = f'https://polymarket.com/event/{slug}'
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = self.session.get(market_url, headers=headers, timeout=self.config.REQUEST_TIMEOUT)
            if response.status_code != 200:
                return None
            
            html_content = response.text
            
            # 1. Primary Pattern: __NEXT_DATA__ JSON parsing (Most accurate)
            next_data_pattern = r'__NEXT_DATA__[^>]*>([^<]+)</script>'
            json_matches = re.findall(next_data_pattern, html_content)
            
            for json_match in json_matches:
                try:
                    json_data = json.loads(json_match)
                    # [STRICT-FIRST] Search specifically for the slug within props to ensure we're looking at the right market data
                    if "props" in json_data and "pageProps" in json_data["props"]:
                        page_props = json_data["props"]["pageProps"]
                        dehydrated = page_props.get("dehydratedState", {})
                        
                        # Loop through queries and find the one that matches our slug
                        for query in dehydrated.get("queries", []):
                            query_key = str(query.get("queryKey", ""))
                            # The query key usually contains the slug: ["markets", "btc-updown-5m-1773375300"]
                            if slug in query_key:
                                data = query.get("state", {}).get("data", {})
                                if isinstance(data, dict):
                                    # Prefer priceToBeat first, then openPrice
                                    if "priceToBeat" in data and data["priceToBeat"]:
                                        return float(str(data["priceToBeat"]).replace(',', ''))
                                    if "openPrice" in data and data["openPrice"]:
                                        return float(str(data["openPrice"]).replace(',', ''))
                        
                        # Fallback within pageProps if not in dehydrated queries
                        market_info = page_props.get("market", {})
                        if isinstance(market_info, dict) and market_info.get("slug") == slug:
                            p2b = market_info.get("priceToBeat") or market_info.get("openPrice")
                            if p2b: return float(str(p2b).replace(',', ''))

                    # [FALLBACK] If no slug match found in queries, we DO NOT search globally 
                    # as it often picks up unrelated markets. Return None and let API/Cache handle it.
                    pass
                except (json.JSONDecodeError, ValueError):
                    continue

            # 2. Final Fallback: Only if we're desperate and we can find a VERY specific pattern 
            # associated with the slug (not just a global "priceToBeat")
            # For now, we prefer returning None to returning a wild $1900-off price.
            return None
            
        except Exception as e:
            self.log(f"[yellow]Web Extraction Failed for {slug}: {e}[/]")
            return None

    def fetch_polymarket(self, slug, force_refresh=False):
        # Initialize default values to prevent scope errors
        up_bid = down_bid = up_ask = down_ask = 0.5
        up_id = down_id = None
        m = {}  # Initialize m to prevent scope errors
        
        try:
            r = self.session.get(f"https://gamma-api.polymarket.com/markets/slug/{slug}", timeout=self.config.REQUEST_TIMEOUT)
            r.raise_for_status()
            m = r.json()
            ids = m["clobTokenIds"] if isinstance(m["clobTokenIds"], list) else json.loads(m["clobTokenIds"])
            outs = m["outcomes"] if isinstance(m["outcomes"], list) else json.loads(m["outcomes"])
            
            # Robust outcome check
            idx_up, idx_down = None, None
            for i, o in enumerate(outs):
                o_low = str(o).lower()
                if any(x in o_low for x in ["up", "yes", "above", "higher", "top"]):
                    idx_up = i
                elif any(x in o_low for x in ["down", "no", "below", "lower", "bottom"]):
                    idx_down = i
            
            if idx_up is not None and idx_down is not None:
                up_id, down_id = ids[idx_up], ids[idx_down]
            else:
                up_id, down_id = ids[0], ids[1]
            
            def get_p(tid, side):
                try: 
                    return float(requests.get("https://clob.polymarket.com/price", params={"token_id":tid,"side":side}, timeout=1.5).json().get("price",0))
                except: return 0
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                f_ua = executor.submit(get_p, up_id, "buy")
                f_da = executor.submit(get_p, down_id, "buy")
                f_ub = executor.submit(get_p, up_id, "sell")
                f_db = executor.submit(get_p, down_id, "sell")
                
                up_ask, down_ask = f_ua.result(), f_da.result()
                up_bid, down_bid = f_ub.result(), f_db.result()

            if not getattr(self, "app_active", False): return m

            # Volume at Open (Binance)
            curr_t = time.time()
            if curr_t - getattr(self, "last_vol_update", 0) > 5:
                try:
                    b_depth = requests.get("https://api.binance.com/api/v3/depth", params={"symbol": "BTCUSDT", "limit": 1000}, timeout=1.5).json()
                    open_p = self.market_data.get("btc_open", 0)
                    if open_p > 0:
                        self.market_data["vol_up"] = sum(float(b[1]) for b in b_depth.get("bids", []) if float(b[0]) >= open_p)
                        self.market_data["vol_dn"] = sum(float(a[1]) for a in b_depth.get("asks", []) if float(a[0]) <= open_p)
                    self.last_vol_update = curr_t
                except: pass

        except Exception as e:
            self.log(f"[red]Poly Fetch Error ({slug}): {e}[/]", is_connection_error=True)
            # Ensure we have fallback values even if API completely fails
            if up_id is None:
                up_id, down_id = "unknown_up", "unknown_down"
        
        # Best Estimate of 'Current Price'
        def _best(b, a):
            if b > 0 and a > 0: return (b+a)/2
            return a or b or 0.5

        # Final P2B and Resolution Extraction
        p2b = m.get("priceToBeat")
        resolution_status = m.get("umaResolutionStatus", "unknown")
        is_closed = m.get("closed", False)
        
        # Outcome Prices (as parsed list)
        op_raw = m.get("outcomePrices")
        outcome_prices = []
        if op_raw:
            try: outcome_prices = op_raw if isinstance(op_raw, list) else json.loads(op_raw)
            except: pass

        # Deep search for high-precision P2B in event metadata
        if p2b is None and m.get("events"):
            evt = m["events"][0]
            if "eventMetadata" in evt:
                raw_p2b = evt["eventMetadata"].get("priceToBeat")
                if raw_p2b:
                    try: p2b = float(str(raw_p2b).replace(',', ''))
                    except: p2b = None
        
        # [REFIX] Fallback to HTML scraping if API fails to provide priceToBeat
        if p2b is None:
            now = time.time()
            # Check cache first if not forcing a refresh
            # REFINEMENT: If force_refresh is True, we only skip if the cache is VERY fresh (< 5s)
            is_very_fresh = (now - self._scraped_p2b_fail_ts.get(slug, 0)) < 5
            
            if not force_refresh and slug in self._scraped_p2b_cache:
                p2b = self._scraped_p2b_cache[slug]
            elif not force_refresh and (now - self._scraped_p2b_fail_ts.get(slug, 0)) < 60:
                # Rate limit failures to avoid slamming web every tick (60s cooldown)
                pass
            elif force_refresh and is_very_fresh:
                # Even for audit, if we just scraped this slug 5 seconds ago, don't re-scrape
                p2b = self._scraped_p2b_cache.get(slug)
                if p2b:
                    self.log(f"[dim]Audit: Using recently scraped P2B for {slug} (${p2b:,.2f})[/]")
            else:
                p2b = self._extract_price_to_beat_from_web(slug)
                if p2b:
                    # Log ONLY if it's a NEW entry or a FORCE refresh to avoid spam
                    is_new = (slug not in self._scraped_p2b_cache)
                    self._scraped_p2b_cache[slug] = p2b
                    if is_new or force_refresh:
                        label = "Audit (Fresh)" if force_refresh else "Scrape (New)"
                        self.log(f"[cyan]{label}: P2B scraped from web for {slug}: ${p2b:,.2f}[/]")
                else:
                    # Record failure timestamp for negative cache
                    self._scraped_p2b_fail_ts[slug] = now

        return {
            "up_price": _best(up_bid, up_ask), 
            "down_price": _best(down_bid, down_ask),
            "up_bid": up_bid, "down_bid": down_bid,
            "up_ask": up_ask, "down_ask": down_ask,
            "up_id": up_id, "down_id": down_id,
            "vol_up": self.market_data.get("vol_up", 0),
            "vol_dn": self.market_data.get("vol_dn", 0),
            "p2b": p2b,
            "resolution_status": resolution_status,
            "is_closed": is_closed,
            "outcome_prices": outcome_prices
        }
