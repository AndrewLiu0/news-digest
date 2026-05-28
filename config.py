# Strict Source Tiers based on Timeline Sources Aug 2025
SOURCE_TIER = {
    # --- US Government ---
    "state.gov": 1,
    "dhs.gov": 1,
    "defense.gov": 1,
    "commerce.gov": 1,
    "whitehouse.gov": 1,
    "treasury.gov": 1,
    "ustr.gov": 1,
    "china.usembassy-china.org.cn": 1,
    "justice.gov": 1,
    "house.gov": 1,
    "senate.gov": 1,
    "energy.gov": 1,
    "usda.gov": 1,
    "fcc.gov": 1,
    "sec.gov": 1,
    "cisa.gov": 1,
    "bis.doc.gov": 1,
    "fbi.gov": 1,
    "congress.gov": 1,
    "navy.mil": 1,
    "army.mil": 1,
    "af.mil": 1,

    # --- Chinese Government ---
    "fmprc.gov.cn": 1,
    "mofcom.gov.cn": 1, 
    "mod.gov.cn": 1,
    "gov.cn": 1,
    "ndrc.gov.cn": 1,
    "miit.gov.cn": 1,
    "pbc.gov.cn": 1,
    "customs.gov.cn": 1,
    "cac.gov.cn": 1,
    "gwytb.gov.cn": 1,
    "mfa.gov.cn": 1,
    "npc.gov.cn": 1,
    "scio.gov.cn": 1,

    # --- News Outlets (Requested) ---
    "reuters.com": 1,
    "bloomberg.com": 1,
    "foxnews.com": 1,
    "cnbc.com": 1,
    "scmp.com": 1
}

ALLOWED_DOMAINS = set(SOURCE_TIER.keys())

# Targeted URLs from Timeline Sources Document
OFFICIAL_PAGES = [
    # US Government
    "https://www.state.gov/press-releases/",
    "https://www.state.gov/countries-areas/china/",
    "https://www.state.gov/countries-areas-archive/china/",
    "https://www.state.gov/department-press-briefings/",
    "https://www.dhs.gov/news-releases/press-releases",
    "https://www.defense.gov/News/Press-Products/",
    "https://www.commerce.gov/news/press-releases",
    "https://www.whitehouse.gov/news/",
    "https://home.treasury.gov/news/press-releases",
    "https://ustr.gov/about-us/policy-offices/press-office/press-releases",
    "https://china.usembassy-china.org.cn/news/",
    "https://www.justice.gov/news/press-releases",
    "https://chinaselectcommittee.house.gov/media/press-releases",
    "https://www.uscc.gov/hearings-all",
    
    # Chinese Government
    "https://www.fmprc.gov.cn/eng/zy/jj/dstzgzz/dszs/",
    "https://www.fmprc.gov.cn/eng/xw/fyrbt/",
    "https://www.fmprc.gov.cn/eng/gjhdq_665435/3376_665447/3432_664920/3435_664926/",
    "https://www.fmprc.gov.cn/eng/xw/zwbd/",
    "https://english.mofcom.gov.cn/News/index.html",
    "http://eng.mod.gov.cn/2025xb/N/T/index.html",
    "http://eng.mod.gov.cn/2025xb/N/I/index.html",
    "http://eng.mod.gov.cn/2025xb/N/JE/index.html",
    "http://eng.mod.gov.cn/2025xb/P/index.html",
    "http://english.www.gov.cn/news/",
    "https://www.fmprc.gov.cn/mfa_eng/",
    "https://en.ndrc.gov.cn/news/",
    "http://www.arats.com.cn/yw/",
    "https://www.gwytb.gov.cn/xwdt/",

    # News Outlets
    "https://www.reuters.com/world/china/",
    "https://www.bloomberg.com/china",
    "https://www.foxnews.com/category/world/china",
    "https://www.cnbc.com/china-politics/",
    "https://www.scmp.com/news/china"
]

# Targeted Chinese State Media Pages
STATE_MEDIA_PAGES = [
    "http://www.xinhuanet.com/english/world/index.htm",
    "http://en.people.cn/90785/index.html",
    "https://www.globaltimes.cn/china/politics/index.html"
]

# RSS Feeds
RSS_FEEDS = [
    "https://www.miit.gov.cn/api-gateway/jpaas-plugins-web-server/front/rss/getinfo?webId=8d828e408d90447786ddbe128d495e9e&columnIds=d3e2bede1bc045e2875fc7161c01db7d,028da85b0dbd4c9cb96fd5f421cd32b8,e4d6c56063fa4edca257cc2e24ad473c,161ae25e72be496f93cd1c1a79f5cc2b,ca517c97303b40cf80bd668b35f6148f",
    "https://www.state.gov/feed/",
    "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945",
    "https://ustr.gov/rss.xml",
    "https://www.reutersagency.com/feed/?best-topics=china&post_type=best",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html" # CNBC China News
]

# Discovery Queries
DOC_QUERY     = '"United States" "China" (domain:gov OR domain:gov.cn OR domain:reuters.com OR domain:bloomberg.com OR domain:foxnews.com OR domain:cnbc.com)'
CONTEXT_QUERY = '"United States" "China" (domain:gov OR domain:gov.cn OR domain:reuters.com OR domain:bloomberg.com OR domain:foxnews.com OR domain:cnbc.com)'
GNEWS_QUERY   = 'United States China (site:gov OR site:gov.cn OR site:reuters.com OR site:bloomberg.com OR site:foxnews.com OR site:cnbc.com) when:10d'

RSS_KEYWORDS = [
    "US", "U.S.", "CHINA", "CHINESE", "TAIWAN", "SINO", "BEIJING", "WASHINGTON",
    "美", "中", "台", "北京", "华盛顿", "制裁", "关税", "贸易", "芯片", "半导体"
]

# --- Global Settings ---
LOOKBACK_DAYS = 7
MAX_TOTAL_ARTICLES = 250  # Total articles in the final report

# --- Processing & Limit Settings ---
MAX_RELEVANCE_CHECK = 300      # Optimized for cost/quality balance
MAX_DEEP_DIVE_COUNT = 15      # Focused on the most critical items
MAX_WORKERS = 30               # Increased parallel workers for faster runtime

# --- Discovery Limits ---
TAVILY_MAX_RESULTS = 50
GDELT_MAX_RECORDS = 250
GNEWS_MAX_RESOLVE = 250        # Max GNews results to resolve to final URLs

# --- Source Toggles ---
ENABLE_GDELT = True
ENABLE_RSS = True
ENABLE_TAVILY = True
ENABLE_GOOGLE_NEWS = True
ENABLE_CHINESE_STATE_MEDIA = True
ENABLE_OFFICIAL_SCRAPE = True
ENABLE_RAW_SOURCE_LIST = True # If True, saves a source list BEFORE strategic deduplication