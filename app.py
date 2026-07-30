import random
import urllib.parse

import requests
import streamlit as st
import streamlit.components.v1 as components

# =============================
# CONFIG
# =============================
# NOTE: `"remote_url" or "local_url"` in Python always picks the first string
# (truthy short-circuit), so a local fallback written that way silently never
# fires. Toggle explicitly instead.
USE_LOCAL_API = False  # set True while testing with `uvicorn main:app --reload`

REMOTE_API_BASE = "https://movie-rec-466x.onrender.com"
LOCAL_API_BASE = "http://127.0.0.1:8000"
API_BASE = LOCAL_API_BASE if USE_LOCAL_API else REMOTE_API_BASE

TMDB_IMG = "https://image.tmdb.org/t/p/w500"
CATEGORIES = ["trending", "popular", "top_rated", "now_playing", "upcoming"]

st.set_page_config(
    page_title="CineMatch — Movie Recommender",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================
# CURSOR GLOW + CLICK RIPPLE (injected into the parent page, once)
# =============================
components.html(
    """
    <script>
    try {
      const doc = window.parent.document;
      if (!window.parent.__cinematchInit) {
        window.parent.__cinematchInit = true;

        const glow = doc.createElement('div');
        glow.id = 'cinematch-glow';
        Object.assign(glow.style, {
          position: 'fixed', top: '0', left: '0', width: '520px', height: '520px',
          borderRadius: '50%', pointerEvents: 'none', zIndex: '0',
          background: 'radial-gradient(circle, rgba(255,75,110,0.16), rgba(255,154,60,0.07) 40%, transparent 70%)',
          transform: 'translate(-50%,-50%)', transition: 'opacity 0.3s ease', opacity: '0'
        });
        doc.body.appendChild(glow);

        doc.addEventListener('mousemove', function (e) {
          glow.style.left = e.clientX + 'px';
          glow.style.top = e.clientY + 'px';
          glow.style.opacity = '1';
        });
        doc.addEventListener('mouseleave', function () { glow.style.opacity = '0'; });

        doc.addEventListener('click', function (e) {
          const ripple = doc.createElement('div');
          Object.assign(ripple.style, {
            position: 'fixed', left: e.clientX + 'px', top: e.clientY + 'px',
            width: '12px', height: '12px', marginLeft: '-6px', marginTop: '-6px',
            borderRadius: '50%', pointerEvents: 'none', zIndex: '9999',
            border: '2px solid rgba(255,75,110,0.65)', transform: 'scale(0)',
            transition: 'transform 0.6s ease, opacity 0.6s ease', opacity: '1'
          });
          doc.body.appendChild(ripple);
          requestAnimationFrame(() => {
            ripple.style.transform = 'scale(7)';
            ripple.style.opacity = '0';
          });
          setTimeout(() => ripple.remove(), 650);
        });
      }
    } catch (err) { /* silently ignore, e.g. sandboxed browsers */ }
    </script>
    """,
    height=0,
)

# =============================
# STYLES
# =============================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Animated ambient background blobs */
.stApp { background: #0e1117; overflow-x: hidden; }
.stApp::before, .stApp::after {
    content: ''; position: fixed; width: 620px; height: 620px; border-radius: 50%;
    filter: blur(130px); z-index: 0; opacity: 0.32; pointer-events: none;
}
.stApp::before { background: #ff4b6e; top: -220px; left: -160px; animation: float1 18s ease-in-out infinite; }
.stApp::after  { background: #3c8cff; bottom: -220px; right: -160px; animation: float2 22s ease-in-out infinite; }
@keyframes float1 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(130px,90px) scale(1.15); } }
@keyframes float2 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-110px,-70px) scale(1.1); } }

.block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1450px; position: relative; z-index: 1; }

/* Header */
.app-header { display: flex; align-items: center; gap: 14px; margin-bottom: 0.2rem; }
.app-title {
    font-family: 'Poppins', sans-serif; font-weight: 700; font-size: 2.4rem;
    background: linear-gradient(90deg, #ff4b6e, #ff9a3c, #ffd166, #ff4b6e);
    background-size: 300% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    animation: shimmer 6s linear infinite; margin: 0;
}
@keyframes shimmer { to { background-position: 300% center; } }
.app-subtitle { color: #9ca3af; font-size: 0.95rem; margin-top: -6px; margin-bottom: 1.2rem; }

/* Section headers */
.section-title {
    font-family: 'Poppins', sans-serif; font-weight: 600; font-size: 1.25rem;
    margin: 1.4rem 0 0.8rem 0; display: flex; align-items: center; gap: 8px;
}

/* Buttons */
.stButton>button {
    border-radius: 10px; border: 1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.04); transition: all 0.25s ease;
}
.stButton>button:hover {
    border-color: #ff4b6e; color: #ff4b6e;
    box-shadow: 0 0 14px rgba(255,75,110,0.45); transform: translateY(-2px);
}

/* Movie card */
.movie-card {
    border-radius: 14px; overflow: hidden; background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.movie-card:hover {
    transform: translateY(-6px) scale(1.015);
    box-shadow: 0 16px 36px rgba(255,75,110,0.22);
    border-color: rgba(255,75,110,0.45);
}

/* Poster hover effect: zoom + darken + glowing ring + play icon */
.poster-wrap { position: relative; overflow: hidden; border-radius: 14px 14px 0 0; cursor: pointer; }
.poster-wrap img { cursor: pointer; transition: transform 0.4s ease, filter 0.4s ease; display: block; }
.poster-wrap:hover img {
    transform: scale(1.08);
    filter: brightness(0.55) saturate(1.1);
}
.poster-wrap::after {
    content: '▶';
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%,-50%) scale(0.6);
    font-size: 2.2rem; color: #ffffff;
    opacity: 0; transition: opacity 0.3s ease, transform 0.3s ease;
    pointer-events: none;
    text-shadow: 0 0 20px rgba(255,75,110,0.9);
}
.poster-wrap:hover::after { opacity: 1; transform: translate(-50%,-50%) scale(1); }
.poster-wrap::before {
    content: ''; position: absolute; inset: 0; border-radius: 14px 14px 0 0;
    box-shadow: inset 0 0 0 0 rgba(255,75,110,0.8);
    transition: box-shadow 0.3s ease; pointer-events: none;
}
.poster-wrap:hover::before { box-shadow: inset 0 0 0 3px rgba(255,75,110,0.8); }

.movie-title { font-size: 0.88rem; font-weight: 500; line-height: 1.2rem; height: 2.4rem; overflow: hidden; padding: 0 10px; margin-top: 6px; }
.movie-meta { font-size: 0.75rem; color: #9ca3af; padding: 0 10px 6px 10px; }

/* Details hero card */
.detail-card {
    border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 22px;
    background: linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.01));
}
.pill {
    display: inline-block; padding: 3px 12px; border-radius: 999px;
    background: rgba(255,75,110,0.15); color: #ff9ab0; font-size: 0.78rem;
    margin-right: 6px; margin-bottom: 4px;
}
.small-muted { color: #9ca3af; font-size: 0.92rem; }
hr { border-color: rgba(255,255,255,0.08); }

/* Sidebar badge */
.badge {
    display: inline-block; background: #ff4b6e; color: white; border-radius: 999px;
    padding: 0 8px; font-size: 0.75rem; font-weight: 600; margin-left: 6px;
}
</style>
""",
    unsafe_allow_html=True,
)

# =============================
# STATE + ROUTING
# =============================
if "view" not in st.session_state:
    st.session_state.view = "home"  # home | details | favorites
if "selected_tmdb_id" not in st.session_state:
    st.session_state.selected_tmdb_id = None
if "favorites" not in st.session_state:
    st.session_state.favorites = {}  # tmdb_id -> card dict
if "recently_viewed" not in st.session_state:
    st.session_state.recently_viewed = []  # list of card dicts, most recent first

qp_view = st.query_params.get("view")
qp_id = st.query_params.get("id")
if qp_view in ("home", "details", "favorites"):
    st.session_state.view = qp_view
if qp_id:
    try:
        st.session_state.selected_tmdb_id = int(qp_id)
        st.session_state.view = "details"
    except ValueError:
        pass


def goto_home():
    st.session_state.view = "home"
    st.query_params["view"] = "home"
    if "id" in st.query_params:
        del st.query_params["id"]
    st.rerun()


def goto_favorites():
    st.session_state.view = "favorites"
    st.query_params["view"] = "favorites"
    if "id" in st.query_params:
        del st.query_params["id"]
    st.rerun()


def goto_details(tmdb_id, card=None):
    st.session_state.view = "details"
    st.session_state.selected_tmdb_id = int(tmdb_id)
    st.query_params["view"] = "details"
    st.query_params["id"] = str(int(tmdb_id))
    if card:
        remember_recent(card)
    st.rerun()


def remember_recent(card):
    if not card.get("tmdb_id"):
        return
    st.session_state.recently_viewed = [
        c for c in st.session_state.recently_viewed if c["tmdb_id"] != card["tmdb_id"]
    ]
    st.session_state.recently_viewed.insert(0, card)
    st.session_state.recently_viewed = st.session_state.recently_viewed[:12]


def toggle_favorite(card):
    tmdb_id = card.get("tmdb_id")
    if not tmdb_id:
        return
    if tmdb_id in st.session_state.favorites:
        del st.session_state.favorites[tmdb_id]
    else:
        st.session_state.favorites[tmdb_id] = card


# =============================
# API HELPERS
# =============================
@st.cache_data(ttl=30)
def api_get_json(path, params=None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=25)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        return r.json(), None
    except Exception as e:
        return None, f"Request failed: {e}"


def sort_cards(cards, sort_option):
    if sort_option == "Rating: High to Low":
        return sorted(cards, key=lambda x: (x.get("vote_average") or 0), reverse=True)
    if sort_option == "Newest first":
        return sorted(cards, key=lambda x: (x.get("release_date") or ""), reverse=True)
    return cards


def filter_by_rating(cards, min_rating):
    if not min_rating:
        return cards
    return [c for c in cards if (c.get("vote_average") or 0) >= min_rating]


def poster_grid(cards, cols=6, key_prefix="grid"):
    if not cards:
        st.info("No movies to show.")
        return

    rows = (len(cards) + cols - 1) // cols
    idx = 0
    for r in range(rows):
        colset = st.columns(cols)
        for c in range(cols):
            if idx >= len(cards):
                break
            m = cards[idx]
            idx += 1

            tmdb_id = m.get("tmdb_id")
            title = m.get("title", "Untitled")
            poster = m.get("poster_url")
            year = (m.get("release_date") or "")[:4]
            rating = m.get("vote_average")

            with colset[c]:
                st.markdown("<div class='movie-card'>", unsafe_allow_html=True)
                if poster:
                    st.markdown(
                        f"<div class='poster-wrap'><img src='{poster}' "
                        f"style='width:100%;height:auto;display:block;' /></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div class='poster-wrap' style='height:280px;display:flex;"
                        "align-items:center;justify-content:center;color:#6b7280;'>"
                        "🖼️ No poster</div>",
                        unsafe_allow_html=True,
                    )

                st.markdown(f"<div class='movie-title'>{title}</div>", unsafe_allow_html=True)
                meta_bits = []
                if year:
                    meta_bits.append(year)
                if rating:
                    meta_bits.append(f"⭐ {rating:.1f}")
                if meta_bits:
                    st.markdown(
                        f"<div class='movie-meta'>{' · '.join(meta_bits)}</div>",
                        unsafe_allow_html=True,
                    )

                b1, b2 = st.columns([1, 2])
                with b1:
                    is_fav = tmdb_id in st.session_state.favorites
                    if st.button(
                        "❤" if is_fav else "🤍",
                        key=f"{key_prefix}_fav_{r}_{c}_{idx}_{tmdb_id}",
                        use_container_width=True,
                        help="Remove from favorites" if is_fav else "Add to favorites",
                    ):
                        toggle_favorite(m)
                        st.rerun()
                with b2:
                    if st.button(
                        "Details",
                        key=f"{key_prefix}_open_{r}_{c}_{idx}_{tmdb_id}",
                        use_container_width=True,
                    ):
                        if tmdb_id:
                            goto_details(tmdb_id, m)
                st.markdown("</div>", unsafe_allow_html=True)


def to_cards_from_tfidf_items(tfidf_items):
    cards = []
    for x in tfidf_items or []:
        tmdb = x.get("tmdb") or {}
        if tmdb.get("tmdb_id"):
            cards.append(
                {
                    "tmdb_id": tmdb["tmdb_id"],
                    "title": tmdb.get("title") or x.get("title") or "Untitled",
                    "poster_url": tmdb.get("poster_url"),
                    "release_date": tmdb.get("release_date"),
                    "vote_average": tmdb.get("vote_average"),
                }
            )
    return cards


def parse_tmdb_search_to_cards(data, keyword, limit=24):
    """
    Supports BOTH API shapes:
      1) raw TMDB: {"results":[{id,title,poster_path,...}]}
      2) list cards: [{tmdb_id,title,poster_url,...}]
    """
    keyword_l = keyword.strip().lower()
    raw_items = []

    if isinstance(data, dict) and "results" in data:
        for m in data.get("results") or []:
            title = (m.get("title") or "").strip()
            tmdb_id = m.get("id")
            poster_path = m.get("poster_path")
            if not title or not tmdb_id:
                continue
            raw_items.append(
                {
                    "tmdb_id": int(tmdb_id),
                    "title": title,
                    "poster_url": f"{TMDB_IMG}{poster_path}" if poster_path else None,
                    "release_date": m.get("release_date", ""),
                    "vote_average": m.get("vote_average"),
                }
            )
    elif isinstance(data, list):
        for m in data:
            tmdb_id = m.get("tmdb_id") or m.get("id")
            title = (m.get("title") or "").strip()
            poster_url = m.get("poster_url")
            if not title or not tmdb_id:
                continue
            raw_items.append(
                {
                    "tmdb_id": int(tmdb_id),
                    "title": title,
                    "poster_url": poster_url,
                    "release_date": m.get("release_date", ""),
                    "vote_average": m.get("vote_average"),
                }
            )
    else:
        return [], []

    matched = [x for x in raw_items if keyword_l in x["title"].lower()]
    final_list = matched if matched else raw_items

    suggestions = []
    for x in final_list[:10]:
        year = (x.get("release_date") or "")[:4]
        label = f"{x['title']} ({year})" if year else x["title"]
        suggestions.append((label, x["tmdb_id"]))

    cards = [
        {
            "tmdb_id": x["tmdb_id"],
            "title": x["title"],
            "poster_url": x["poster_url"],
            "release_date": x.get("release_date"),
            "vote_average": x.get("vote_average"),
        }
        for x in final_list[:limit]
    ]
    return suggestions, cards


# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## 🎬 CineMatch")
    st.caption("Discover movies you'll actually like.")

    if st.button("🏠 Home", use_container_width=True):
        goto_home()

    fav_count = len(st.session_state.favorites)
    fav_label = f"❤️ Favorites ({fav_count})" if fav_count else "❤️ Favorites"
    if st.button(fav_label, use_container_width=True):
        goto_favorites()

    st.markdown("---")
    st.markdown("### 🏠 Home Feed")
    home_category = st.selectbox(
        "Category", CATEGORIES, index=0, format_func=lambda x: x.replace("_", " ").title()
    )
    grid_cols = st.slider("Grid columns", 4, 8, 6)

    st.markdown("---")
    if st.button("🎲 Surprise Me!", use_container_width=True):
        pick_category = random.choice(CATEGORIES)
        surprise_data, s_err = api_get_json(
            "/home", params={"category": pick_category, "limit": 24}
        )
        if not s_err and surprise_data:
            pick = random.choice(surprise_data)
            st.balloons()
            goto_details(pick.get("tmdb_id"), pick)
        else:
            st.warning("Couldn't fetch a surprise right now — try again.")

    st.markdown("---")
    st.caption(f"API: `{API_BASE}`")

    if st.session_state.recently_viewed:
        st.markdown("---")
        st.markdown("### 🕘 Recently Viewed")
        for rv in st.session_state.recently_viewed[:5]:
            rc1, rc2 = st.columns([1, 2])
            with rc1:
                if rv.get("poster_url"):
                    st.markdown(
                        f"<img src='{rv['poster_url']}' style='width:100%;border-radius:6px;"
                        f"cursor:pointer;' />",
                        unsafe_allow_html=True,
                    )
                else:
                    st.write("🖼️")
            with rc2:
                st.caption((rv.get("title") or "Untitled")[:24])
                if st.button("Open", key=f"sidebar_recent_{rv.get('tmdb_id')}", use_container_width=True):
                    goto_details(rv.get("tmdb_id"), rv)

# =============================
# HEADER
# =============================
st.markdown(
    """
<div class="app-header">
    <span style="font-size:2.2rem;">🎬</span>
    <h1 class="app-title">CineMatch</h1>
</div>
""",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='app-subtitle'>Type a keyword → get suggestions & matching results "
    "→ open a movie → see similar picks, genre matches, and a trailer link.</div>",
    unsafe_allow_html=True,
)
st.divider()

# ==========================================================
# VIEW: HOME
# ==========================================================
if st.session_state.view == "home":
    typed = st.text_input(
        "🔍 Search by movie title", placeholder="Try: avengers, batman, inception..."
    )

    with st.expander("⚙️ Filters & sort"):
        f1, f2 = st.columns(2)
        with f1:
            sort_option = st.selectbox(
                "Sort by", ["Relevance", "Rating: High to Low", "Newest first"]
            )
        with f2:
            min_rating = st.slider("Minimum rating", 0.0, 10.0, 0.0, 0.5)

    st.divider()

    if typed.strip():
        if len(typed.strip()) < 2:
            st.caption("Type at least 2 characters for suggestions.")
        else:
            with st.spinner("Searching TMDB..."):
                data, err = api_get_json("/tmdb/search", params={"query": typed.strip()})

            if err or data is None:
                st.error(f"Search failed: {err}")
            else:
                suggestions, cards = parse_tmdb_search_to_cards(data, typed.strip(), limit=24)
                cards = filter_by_rating(cards, min_rating)
                cards = sort_cards(cards, sort_option)

                if suggestions:
                    labels = ["-- Select a movie --"] + [s[0] for s in suggestions]
                    selected = st.selectbox("Suggestions", labels, index=0)
                    if selected != "-- Select a movie --":
                        label_to_id = {s[0]: s[1] for s in suggestions}
                        sel_id = label_to_id[selected]
                        sel_card = next(
                            (c for c in cards if c["tmdb_id"] == sel_id), {"tmdb_id": sel_id}
                        )
                        goto_details(sel_id, sel_card)
                else:
                    st.info("No suggestions found. Try another keyword.")

                st.markdown("<div class='section-title'>🎞️ Results</div>", unsafe_allow_html=True)
                poster_grid(cards, cols=grid_cols, key_prefix="search_results")

        st.stop()

    # HOME FEED MODE
    st.markdown(
        f"<div class='section-title'>🏠 {home_category.replace('_', ' ').title()}</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Loading movies..."):
        home_cards, err = api_get_json("/home", params={"category": home_category, "limit": 24})

    if err or not home_cards:
        st.error(f"Home feed failed: {err or 'Unknown error'}")
        st.stop()

    home_cards = filter_by_rating(home_cards, min_rating)
    home_cards = sort_cards(home_cards, sort_option)
    poster_grid(home_cards, cols=grid_cols, key_prefix="home_feed")

    # RECENTLY VIEWED — always last on the page
    if st.session_state.recently_viewed:
        st.divider()
        st.markdown("<div class='section-title'>🕘 Recently Viewed</div>", unsafe_allow_html=True)
        poster_grid(st.session_state.recently_viewed, cols=grid_cols, key_prefix="recent")

# ==========================================================
# VIEW: FAVORITES
# ==========================================================
elif st.session_state.view == "favorites":
    a, b = st.columns([1, 3])
    with a:
        if st.button("← Back to Home", use_container_width=True):
            goto_home()
    with b:
        st.markdown("<div class='section-title'>❤️ Your Favorites</div>", unsafe_allow_html=True)

    if not st.session_state.favorites:
        st.info("You haven't saved any movies yet. Tap 🤍 on a card to add it here.")
    else:
        poster_grid(list(st.session_state.favorites.values()), cols=grid_cols, key_prefix="favs")
        st.caption("Favorites are kept for this browser session only.")

# ==========================================================
# VIEW: DETAILS
# ==========================================================
elif st.session_state.view == "details":
    tmdb_id = st.session_state.selected_tmdb_id
    if not tmdb_id:
        st.warning("No movie selected.")
        if st.button("← Back to Home"):
            goto_home()
        st.stop()

    a, b = st.columns([1, 3])
    with a:
        if st.button("← Back to Home", use_container_width=True):
            goto_home()
    with b:
        st.markdown("<div class='section-title'>📄 Movie Details</div>", unsafe_allow_html=True)

    with st.spinner("Loading details..."):
        data, err = api_get_json(f"/movie/id/{tmdb_id}")

    if err or not data:
        st.error(f"Could not load details: {err or 'Unknown error'}")
        st.stop()

    left, right = st.columns([1, 2.4], gap="large")

    with left:
        st.markdown("<div class='detail-card'>", unsafe_allow_html=True)
        if data.get("poster_url"):
            st.markdown(
                f"<div class='poster-wrap' style='border-radius:14px;'>"
                f"<img src='{data['poster_url']}' style='width:100%;height:auto;"
                f"display:block;border-radius:14px;' /></div>",
                unsafe_allow_html=True,
            )
        else:
            st.write("🖼️ No poster")

        is_fav = tmdb_id in st.session_state.favorites
        fav_card = {
            "tmdb_id": tmdb_id,
            "title": data.get("title"),
            "poster_url": data.get("poster_url"),
            "release_date": data.get("release_date"),
        }
        if st.button(
            "❤️ Saved to Favorites" if is_fav else "🤍 Add to Favorites",
            use_container_width=True,
        ):
            toggle_favorite(fav_card)
            st.rerun()

        title_q = urllib.parse.quote_plus(f"{data.get('title', '')} trailer")
        st.link_button(
            "▶️ Watch Trailer on YouTube",
            f"https://www.youtube.com/results?search_query={title_q}",
            use_container_width=True,
        )

        jw_q = urllib.parse.quote_plus(data.get("title", ""))
        st.link_button(
            "📺 Where to Watch (JustWatch)",
            f"https://www.justwatch.com/us/search?q={jw_q}",
            use_container_width=True,
        )
        st.caption(
            "Opens JustWatch's legal streaming guide. It highlights any free "
            "(ad-supported or subscription-included) options alongside paid ones — "
            "availability varies by title and region."
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='detail-card'>", unsafe_allow_html=True)
        st.markdown(f"## {data.get('title', '')}")
        release = data.get("release_date") or "—"
        genres = data.get("genres", []) or []

        st.markdown(f"<div class='small-muted'>📅 Release: {release}</div>", unsafe_allow_html=True)
        if genres:
            pills = "".join(f"<span class='pill'>{g['name']}</span>" for g in genres)
            st.markdown(f"<div style='margin-top:8px;'>{pills}</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### Overview")
        st.write(data.get("overview") or "No overview available.")
        st.markdown("</div>", unsafe_allow_html=True)

    if data.get("backdrop_url"):
        st.markdown("<div class='section-title'>🖼️ Backdrop</div>", unsafe_allow_html=True)
        st.image(data["backdrop_url"], use_container_width=True)

    remember_recent(fav_card)

    st.divider()
    st.markdown("<div class='section-title'>✅ Recommendations</div>", unsafe_allow_html=True)

    title = (data.get("title") or "").strip()
    if title:
        with st.spinner("Finding similar movies..."):
            bundle, err2 = api_get_json(
                "/movie/search",
                params={"query": title, "tfidf_top_n": 12, "genre_limit": 12},
            )

        if not err2 and bundle:
            st.markdown(
                "<div class='section-title'>🔎 Similar Movies (TF-IDF)</div>",
                unsafe_allow_html=True,
            )
            poster_grid(
                to_cards_from_tfidf_items(bundle.get("tfidf_recommendations")),
                cols=grid_cols,
                key_prefix="details_tfidf",
            )

            st.markdown(
                "<div class='section-title'>🎭 More Like This (Genre)</div>",
                unsafe_allow_html=True,
            )
            poster_grid(
                bundle.get("genre_recommendations", []),
                cols=grid_cols,
                key_prefix="details_genre",
            )
        else:
            st.info("Showing genre recommendations (fallback).")
            with st.spinner("Loading fallback recommendations..."):
                genre_only, err3 = api_get_json(
                    "/recommend/genre", params={"tmdb_id": tmdb_id, "limit": 18}
                )
            if not err3 and genre_only:
                poster_grid(genre_only, cols=grid_cols, key_prefix="details_genre_fallback")
            else:
                st.warning("No recommendations available right now.")
    else:
        st.warning("No title available to compute recommendations.")
