import json, os, re
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)

CHANNELS_URL = "https://iptv-org.github.io/api/channels.json"
LOGOS_URL    = "https://iptv-org.github.io/api/logos.json"

EPG_URLS = [
    "https://iptvx.one/epg/epg_lite.xml.gz",
    "https://epg.one/epg.xml.gz",
    "http://epg.it999.ru/edem.xml.gz",
]
EPG_TTL_HOURS = 168
EPG_TIMEOUT   = 120

CONCURRENCY      = int(os.getenv("IPTV_CONC", "250"))
HOST_CONCURRENCY = 10
HTTP_TIMEOUT     = 4
RANGE_BYTES      = 4096
RETRIES          = 0

WARM_TTL_HOURS         = 6
DEAD_CACHE_MIN_FAILS   = 1
DEAD_CACHE_TTL_DAYS    = 30
HOST_BLOCK_AFTER_FAILS = 3

MIN_ALIVE_ABS  = 20
MIN_ALIVE_PCT  = 0.10
DEEP_CHECK     = os.getenv("DEEP_CHECK") == "1"
TEST_URL       = os.getenv("TEST_URL", "").strip()

PLAYLIST_PATH = ROOT / "playlist.m3u"
README_PATH   = ROOT / "README.md"
REPORT_PATH   = DATA / "report.json"
SOURCES_PATH  = ROOT / "sources.yml"

BAD_URL_PATTERNS = [
    "ads=", "ad=", "adv=", "advert=", "advertisement=",
    "banner=", "promo=", "/ads/", "/ad/",
    "mcquack", "cinerama", "tvstitch", "thestream.cyou", "televizor24.cc"
]

UAS = {
    "Wink": "WINK/RT_(Android_TV/11)_WinkPlayer_AppleWebKit/537.36",
    "HlsWinkPlayer": "HlsWinkPlayer/3.0.2 (Linux; Android 11; Wink) ExoPlayerLib/2.18.1",
    "TiviMate": "TiviMate/4.7.0 (Linux; Android 11; Sony Smart TV)",
    "AndroidTV": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "VLC": "VLC/3.0.20 LibVLC/3.0.20",
    "SmartTV": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/4.0 Chrome/76.0.3809.146 TV Safari/537.36",
    "Kodi": "Kodi/20.5 (Windows NT 10.0; Win64; x64) App_Bitness/64 Version/20.5",
    "OTT": "OTT Navigator/1.7.1.2 (Linux; Android 11)",
    "ExoPlayer": "ExoPlayerLib/2.18.1",
    "Lavf": "Lavf/60.16.100",
    "okhttp": "okhttp/4.9.3",
    "Chrome_Win": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Safari_Mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "MXPlayer": "MXPlayer/1.71.6 (Linux; Android 11)",
}
UA_WEIGHTS = {"Wink":30,"HlsWinkPlayer":25,"TiviMate":12,"AndroidTV":8,"VLC":8,"SmartTV":6,"Kodi":5,"OTT":5,"ExoPlayer":4,"Lavf":3,"okhttp":3,"Chrome_Win":3,"Safari_Mac":2,"Firefox":2,"MXPlayer":2}

BAD_GROUPS = ["kids", "детск", "children", "cartoon", "мульт", "шопинг", "shop", "магазин", "ювелир", "витрина", "adult", "18+", "эротика", "regional", "региональн", "област", "краев", "город", "авто", "auto", "drive", "религ", "церков", "православ", "ислам", "спас", "союз"]

BAD_WORDS = ["детск","kids","child","cartoon","мульт","карусель","disney","nickelodeon","nick jr","boomerang","смешарик","фиксики","малыш","tiji","аниме","мама","солнце","тамыр","супергерои","радость моя","ani","мультимузыка","капитан фантастика","fan","в гостях у сказки","прима","волга","белгород","самара","енисей","горловка","сочи","пермь","волгоград","корабль","миллет","евразия","нтм","нтс","продвижение","афонтово","омск","новосибирск","нижний","красноярск","прим","братск","новокузнецк","север","сургут","симферополь","луганск","тонус","вайнах","арис","рязань","астрахань","толк","алушта","салям","кубань","щелков","дагестан","краснодар","абза","апсуа","таврия","архыз","грозный","истоки","югра","москва","ингушетия","ярославль","курай","тдк","регион","тнв","лентв","qazaq","kazakh","uzbek","moldova","belarus","ukrain","armenia","georgia","kyrgyz","tajik","turkmen","azerb","latvia","lithuania","estonia","abkhaz","ossetia","chechnya","ingushetia","dagestan","rtvi","рада","freeдом","свобода","svoboda","tvrain","kentron","kino 2","tv 21","беларус","украин","молдов","казах","узбек","армени","грузи","азерб","латви","литв","эстон","киргиз","таджик","туркмен","израил","сша","usa","европа","europe","international","world","global","shop","шоппинг","магазин","leomax","top shop","витрина","ювелирочка","moy mir","авто","auto","drive","драйв","auto plus","autogid","вера","церков","православ","ислам","спас","3abn","союз","царьград","huzur","tbn","angel","mana","big asia","сарафан","усадьба","univer","ntv law","просвещение","точка отрыва","вместе","rus","загородная","дача","home 4k","zoopark","insayt","ministerstvo","душевное","city eden","время","наш кинопоказ","киносерия","кинопоказ","kinohit","киносвидание","test","demo","promo"]

CATEGORY_MAP = {"sports":"⚽ Спорт","sport":"⚽ Спорт","news":"📰 Новостные","movies":"🎬 Кино","movie":"🎬 Кино","cinema":"🎬 Кино","series":"📺 Сериалы","music":"🎵 Музыкальные","documentary":"🎥 Документальные","history":"🎥 Документальные","science":"🌍 Познавательные","education":"🌍 Познавательные","entertainment":"🎭 Развлекательные","comedy":"🎭 Развлекательные","lifestyle":"🎭 Развлекательные","general":"📡 Федеральные","cooking":"🍳 Кулинарные","food":"🍳 Кулинарные","travel":"🌍 Путешествия","culture":"🎭 Культура","business":"📰 Бизнес","weather":"📰 Погода","classic":"🎭 Классика","outdoor":"🌍 Природа","undefined":"📦 Разное","other":"📦 Разное","misc":"📦 Разное","разное":"📦 Разное"}

KEYWORD_RULES = {"⚽ Спорт": ["спорт","sport","футбол","football","матч","хокке","hockey","теннис","бокс","ufc","mma","арена","биатлон"],"📰 Новостные": ["новост","news","известия","рбк","вести","360","дождь","тасс","lenta","информ"],"🎬 Кино": ["кино","cinema","movie","фильм","film","боевик","комедия","ужас","детектив","премьера","tv1000","кинопоказ","иллюзион","победа"],"📺 Сериалы": ["сериал","series","дорам","драма","мелодрам"],"🎵 Музыкальные": ["music","музык","муз","mtv","vh1","ru.tv","шансон","europa plus","bridge","top hit"],"🎭 Развлекательные": ["развлек","юмор","comedy","шоу","тнт","пятница","суббота","перец"],"🌍 Познавательные": ["science","наука","discovery","nat geo","history","истор","viasat","nano","животн","природа","охота","путешеств"],"🎥 Документальные": ["документ","documental","tlc","dmax","военн","биограф","катастроф"],"🍳 Кулинарные": ["кухня","еда","food","cooking","кулинар"],"🎭 Культура": ["культур","culture","искусств","театр"],"📰 Бизнес": ["бизнес","business","деньги"],"📰 Погода": ["погода","weather"]}

NOISE = {"тв","tv","hd","uhd","fhd","sd","4k","1080p","720p","full","канал","channel","online","live","stream"}
TRANSLIT = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya","ї":"i","є":"e","і":"i","ґ":"g"}

def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

def load_json(path: Path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def host_of(url: str) -> str:
    try: return urlparse(url).netloc.lower().split(":")[0]
    except Exception: return "unknown"

def has_cyr(s: str) -> bool: return bool(re.search(r'[а-яА-ЯёЁ]', s or ''))

def norm_name(s: str) -> str:
    n = (s or "").lower().replace("ё","е").replace("й","и")
    n = re.sub(r'\(.*?\)|\[.*?\]', ' ', n)
    n = re.sub(r'[^a-zа-я0-9\s]', ' ', n)
    return " ".join(w for w in n.split() if w and w not in NOISE)

def translit(s: str) -> str: return "".join(TRANSLIT.get(c, c) for c in (s or ""))

def extract_suffix(tvg_id: str) -> str:
    if not tvg_id or "@" not in tvg_id: return ""
    sfx = tvg_id.split("@", 1)[1]; low = sfx.lower()
    if low == "sd": return ""
    if low.startswith("plus") and low[4:].isdigit(): return "+" + low[4:]
    if low in ("hd","fhd","uhd","4k","1080p","720p"): return sfx.upper()
    return sfx

def normalize_url(u: str) -> str:
    if not u: return ""
    try:
        p = urlparse(u.strip())
        drop = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","fbclid","gclid","ref","source"}
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in drop]
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(q), ""))
    except Exception: return u.strip()
