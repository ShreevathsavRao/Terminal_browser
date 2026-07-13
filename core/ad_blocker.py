"""A lightweight ad / tracker blocker for the embedded QtWebEngine browser.

Blocking works at two levels:

* **Network** — a :class:`QWebEngineUrlRequestInterceptor` drops requests to
  known ad/tracker hosts and to URLs carrying obvious ad markers, so the ad
  never even downloads.
* **Cosmetic** — a small CSS snippet (injected by the browser widget) hides
  the empty placeholders that ad slots leave behind.

The block list is a curated set of the major ad and tracking networks; it is
matched by domain suffix so every sub-domain (``ads.example.com``,
``pagead2.googlesyndication.com`` …) is covered too.
"""

import os

try:
    from qtpy.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    _BASE = QWebEngineUrlRequestInterceptor
except Exception:  # pragma: no cover - depends on environment
    _BASE = object


# Domain suffixes belonging to ad networks, trackers and analytics beacons.
AD_HOSTS = {
    # Google ad / tracking
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "google-analytics.com", "googletagmanager.com", "googletagservices.com",
    "adservice.google.com", "pagead2.googlesyndication.com", "2mdn.net",
    "admob.com", "app-measurement.com",
    # Amazon / IAB / big exchanges
    "amazon-adsystem.com", "adsystem.amazon.com", "rubiconproject.com",
    "pubmatic.com", "openx.net", "criteo.com", "criteo.net", "casalemedia.com",
    "adnxs.com", "appnexus.com", "smartadserver.com", "adform.net",
    "yieldmo.com", "3lift.com", "sharethrough.com", "gumgum.com",
    "indexww.com", "districtm.io", "spotxchange.com", "spotx.tv",
    # Social / tracking pixels
    "facebook.net", "connect.facebook.net", "ads-twitter.com", "analytics.twitter.com",
    "ads.linkedin.com", "px.ads.linkedin.com", "bat.bing.com", "ads.yahoo.com",
    "advertising.com", "adtechus.com", "taboola.com", "outbrain.com",
    "revcontent.com", "mgid.com", "content-ad.net",
    # Analytics / trackers
    "scorecardresearch.com", "quantserve.com", "quantcount.com", "hotjar.com",
    "mouseflow.com", "crazyegg.com", "mixpanel.com", "segment.com",
    "segment.io", "amplitude.com", "fullstory.com", "chartbeat.com",
    "newrelic.com", "nr-data.net", "optimizely.com", "branch.io",
    "adroll.com", "bluekai.com", "krxd.net", "demdex.net", "everesttech.net",
    "moatads.com", "adsafeprotected.com", "serving-sys.com", "flashtalking.com",
    # Pop / redirect / low-quality ad networks
    "popads.net", "popcash.net", "propellerads.com", "onclickads.net",
    "adcash.com", "exoclick.com", "juicyads.com", "trafficjunky.net",
    "hilltopads.net", "adsterra.com", "adnium.com", "poperblocker.com",
    "clickadu.com", "mgcash.com", "media.net", "zedo.com", "adblade.com",
    "bidvertiser.com", "infolinks.com", "chitika.com", "yllix.com",
    # Adult ad networks (very common on video/torrent sites)
    "exosrv.com", "exdynsrv.com", "tsyndicate.com", "tsyndicate.net",
    "ero-advertising.com", "eroadvertising.com", "adspyglass.com",
    "adsterra.net", "a-ads.com", "plugrush.com", "trafficstars.com",
    "tsyndicate.io", "realsrv.com", "popunder.net", "clickaine.com",
    "crakrevenue.com", "awempire.com", "widget-a.com", "ad-maven.com",
    "admaven.com", "clicksgear.com", "pushnest.com", "push-house.com",
    "galaksion.com", "mybetterdl.com", "hilltopads.com", "twinred.com",
    "deliver.tf", "trafficjunky.com",
}

# Strong substrings that mark an ad/tracker request regardless of host.
AD_MARKERS = (
    "/pagead/", "/adsbygoogle", "/gampad/", "/adserver", "/adservice",
    "/doubleclick", "/gtag/js", "/collect?v=", "/beacon?", "/track?",
    "/adframe", "/ad_frame", "/popunder", "/prebid",
    "/adsbygoogle", "/pagead/", "/adserver/", "/adservice/",
    "/vast.xml", "/vpaid/",
)

# CSS that hides the leftover slots ("cosmetic" filtering). Kept intentionally
# specific — broad names like ``.ad`` / ``.adv`` collide with real content
# (e.g. "advanced", "address") and break normal pages.
COSMETIC_CSS = (
    "ins.adsbygoogle,iframe[src*='doubleclick'],iframe[src*='googlesyndication'],"
    "iframe[src*='exoclick'],iframe[src*='trafficjunky'],iframe[src*='juicyads'],"
    "iframe[src*='adnxs'],"
    "iframe[id^='google_ads'],iframe[id*='ad_iframe'],div[id^='google_ads'],"
    "div[id*='-ad-'],div[class*='ad-banner'],div[class*='adbanner'],"
    "div[class*='ad-container'],div[class*='ad-wrapper'],div[class*='adslot'],"
    "div[class*='ad-slot'],div[class*='banner-ad'],div[class*='sponsored'],"
    "[data-ad-slot],[data-adunit],.adsbox,.ad-container,.advertisement,"
    ".ad-wrapper,.sponsored-ad,.exo-native-widget"
    "{display:none!important;visibility:hidden!important;"
    "height:0!important;min-height:0!important;max-height:0!important}"
)


class AdBlocker(_BASE):
    """Intercepts network requests and blocks known ad / tracker traffic."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self.blocked_count = 0
        # User-added domains (persisted), on top of the built-in AD_HOSTS.
        self.user_hosts = set()
        self._load_user_hosts()

    # QtWebEngine calls this for every outgoing request.
    def interceptRequest(self, info):
        if not self.enabled:
            return
        try:
            url = info.requestUrl()
            host = url.host().lower()
            # The user's explicit blocklist always wins, even first-party.
            if self._user_blocked(host):
                info.block(True)
                self.blocked_count += 1
                return
            # Never block first-party requests: a page's own scripts, styles
            # and video streams are not ads, and blocking them is what breaks
            # players (falling back to "View Low/High Qual"). This mirrors how
            # real ad blockers only target third-party ad domains.
            try:
                page_host = info.firstPartyUrl().host().lower()
            except Exception:
                page_host = ""
            if page_host and self._same_site(host, page_host):
                return
            if self._host_blocked(host) or self._marker_blocked(url.toString().lower()):
                info.block(True)
                self.blocked_count += 1
        except Exception:
            pass

    @staticmethod
    def _registrable(host):
        """Best-effort registrable domain: the last two labels of the host."""
        parts = (host or "").split('.')
        if len(parts) < 2:
            return host or ""
        return '.'.join(parts[-2:])

    def _same_site(self, host, page_host):
        """True when a request is first-party to the page it originates from."""
        if not host or not page_host:
            return False
        if host == page_host:
            return True
        if host.endswith('.' + page_host) or page_host.endswith('.' + host):
            return True
        return self._registrable(host) == self._registrable(page_host)

    def _user_blocked(self, host):
        """Match only the user's custom blocklist (incl. parent domains)."""
        if not host or not self.user_hosts:
            return False
        if host in self.user_hosts:
            return True
        parts = host.split('.')
        for i in range(1, len(parts) - 1):
            if '.'.join(parts[i:]) in self.user_hosts:
                return True
        return False

    def _host_blocked(self, host):
        if not host:
            return False
        if host in AD_HOSTS or host in self.user_hosts:
            return True
        # Match any parent domain suffix (ads.foo.example.com -> example.com).
        parts = host.split('.')
        for i in range(1, len(parts) - 1):
            suffix = '.'.join(parts[i:])
            if suffix in AD_HOSTS or suffix in self.user_hosts:
                return True
        return False

    # -- user blocklist (persisted) ---------------------------------------
    @staticmethod
    def normalize_host(text):
        """Turn a pasted URL or domain into a bare host (``example.com``)."""
        h = (text or "").strip().lower()
        if not h:
            return ""
        if "://" in h:
            h = h.split("://", 1)[1]
        h = h.split("/", 1)[0]          # drop any path
        h = h.split("?", 1)[0]
        h = h.split("@")[-1]            # drop credentials
        h = h.split(":", 1)[0]          # drop port
        if h.startswith("www."):
            h = h[4:]
        return h

    def add_host(self, text):
        host = self.normalize_host(text)
        if not host or "." not in host:
            return None
        self.user_hosts.add(host)
        self._save_user_hosts()
        return host

    def remove_host(self, host):
        self.user_hosts.discard(host)
        self._save_user_hosts()

    @staticmethod
    def _user_hosts_path():
        base = os.path.join(os.path.expanduser("~"), ".terminal_browser")
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            pass
        return os.path.join(base, "adblock_custom.txt")

    def _load_user_hosts(self):
        try:
            with open(self._user_hosts_path(), "r", encoding="utf-8") as f:
                for line in f:
                    host = line.strip().lower()
                    if host and not host.startswith("#"):
                        self.user_hosts.add(host)
        except Exception:
            pass

    def _save_user_hosts(self):
        try:
            with open(self._user_hosts_path(), "w", encoding="utf-8") as f:
                f.write("# Custom ad-block domains added from the browser panel\n")
                for host in sorted(self.user_hosts):
                    f.write(host + "\n")
        except Exception:
            pass

    @staticmethod
    def _marker_blocked(full_url):
        return any(marker in full_url for marker in AD_MARKERS)
