"""تصميم الواجهة (CSS)."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

:root{
  --bg:#0a0f1d; --panel:#111830; --panel-2:#16203d; --field:#0d1429;
  --line:rgba(148,163,184,.16); --text:#e8ecf6; --muted:#94a3b8;
  --accent:#4f7cff; --accent-soft:rgba(79,124,255,.12);
  --ok:#34d399; --danger:#f43f5e;
}

/* الخط (بدون لمس خطوط الأيقونات) */
html, body, .stApp, p, li, label, h1, h2, h3, h4, button, input, textarea, select,
[data-testid="stMarkdownContainer"], [data-testid="stChatInput"] textarea
{ font-family:'Cairo', sans-serif !important; }
span[data-testid="stIconMaterial"]{ font-family:'Material Symbols Rounded' !important; }

.stApp{
  color:var(--text);
  background:
    radial-gradient(900px 380px at 50% -12%, rgba(79,124,255,.16), transparent 65%),
    linear-gradient(180deg,#0b1122 0%,#0a0f1d 100%);
  background-attachment:fixed;
}

/* الاتجاه: الحاوية LTR (لتبقى القائمة الجانبية على اليسار) والمحتوى RTL */
.stApp, [data-testid="stAppViewContainer"]{ direction:ltr; }
.block-container, [data-testid="stBottom"], [data-testid="stSidebar"] > div,
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{ direction:rtl; text-align:right; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li{ unicode-bidi:plaintext; text-align:start; }
[data-testid="stTextInput"] input, [data-testid="stChatInput"] textarea{ unicode-bidi:plaintext; text-align:start; }

header[data-testid="stHeader"]{ background:transparent; }
footer, [data-testid="stAppDeployButton"], [data-testid="stMainMenu"]{ visibility:hidden; }
.block-container{ padding-top:2rem; padding-bottom:7rem; }
::selection{ background:rgba(79,124,255,.45); }
::-webkit-scrollbar{ width:8px; height:8px; }
::-webkit-scrollbar-thumb{ background:rgba(148,163,184,.28); border-radius:8px; }

/* الشريط الجانبي */
[data-testid="stSidebar"]{ background:#0d1326; border-right:1px solid var(--line); border-left:none; }
[data-testid="stSidebarUserContent"]{ padding-top:2rem !important; }
.brand{ padding:.2rem 0 1rem; }
.brand b{
  display:block; font-size:1.7rem; font-weight:800; letter-spacing:.02em; line-height:1.2;
  background:linear-gradient(100deg,#fff 20%,#8fb0ff 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.brand small{ color:var(--muted); font-size:.85rem; }
.usercard{
  display:flex; align-items:center; gap:10px; padding:10px 12px; margin-bottom:.9rem;
  background:var(--panel); border:1px solid var(--line); border-radius:14px;
}
.avatar{
  width:38px; height:38px; flex:none; border-radius:50%; display:grid; place-items:center;
  background:linear-gradient(135deg,#4f7cff,#7aa2ff); color:#fff; font-weight:800;
}
.uinfo{ min-width:0; flex:1; }
.uinfo b{ display:block; font-size:.95rem; line-height:1.3; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.uinfo small{ display:block; color:var(--muted); font-size:.75rem; direction:ltr; text-align:right;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.chip{ font-size:.7rem; padding:1px 9px; border-radius:999px; background:var(--accent-soft);
  border:1px solid rgba(79,124,255,.35); color:#a9c0ff; flex:none; }
.side-label{ color:var(--muted); font-size:.78rem; margin:.9rem 0 .3rem; }
.status{ display:flex; align-items:center; gap:8px; color:var(--muted); font-size:.82rem; }
.dot{ width:8px; height:8px; border-radius:50%; background:var(--ok); box-shadow:0 0 0 3px rgba(52,211,153,.18); }
.dot.off{ background:var(--danger); box-shadow:0 0 0 3px rgba(244,63,94,.18); }
.footer{ text-align:center; color:var(--muted); font-size:.78rem; margin-top:1.6rem; opacity:.8; }

/* قائمة المحادثات */
[class*="st-key-conv"] button{
  justify-content:flex-start; min-height:2.5rem; font-weight:500; font-size:.9rem;
  background:transparent; border-color:transparent; color:var(--muted);
}
[class*="st-key-conv"] button:hover{ background:var(--panel); color:var(--text); transform:none; box-shadow:none; }
[class*="st-key-conva_"] button{ background:var(--accent-soft); border-color:rgba(79,124,255,.35); color:#fff; }

/* الصفحة الرئيسية وصفحات الدخول */
.hero{ text-align:center; padding:2.5rem 0 1.8rem; display:flex; flex-direction:column; align-items:center; gap:.7rem; }
.hero-kicker{
  display:inline-flex; align-items:center; gap:8px; padding:4px 14px; border-radius:999px;
  background:var(--accent-soft); border:1px solid rgba(79,124,255,.3); color:#a9c0ff; font-size:.82rem; font-weight:600;
}
.hero-title{ font-size:2.3rem; font-weight:800; line-height:1.35; margin:0; color:#fff; }
.hero-note{ font-size:1rem; color:var(--muted); max-width:34rem; margin:0; line-height:1.9; }
.sg-label{ color:var(--muted); font-size:.85rem; margin:.4rem 0 .6rem; }
.auth-brand{ text-align:center; padding:1.2rem 0 1.4rem; }
.auth-brand b{
  display:block; font-size:2.6rem; font-weight:800; line-height:1.2;
  background:linear-gradient(100deg,#fff 20%,#8fb0ff 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.auth-brand span{ color:var(--muted); font-size:.95rem; }
.page-title{ font-size:1.6rem; font-weight:800; margin:0 0 .2rem; }
.page-sub{ color:var(--muted); font-size:.92rem; margin:0 0 1.2rem; }
.topbar-title{ font-size:1.1rem; font-weight:700; margin:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.topbar-sub{ color:var(--muted); font-size:.8rem; }

/* فقاعات المحادثة */
[data-testid="stChatMessage"]{
  background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:14px 18px; margin-bottom:.7rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){
  background:var(--accent-soft); border-color:rgba(79,124,255,.28);
}
.badge{ display:inline-block; padding:1px 12px; margin:.5rem 0 0 .4rem; border-radius:999px;
  font-size:.78rem; border:1px solid var(--line); color:var(--muted); }
.badge.hi{ border-color:rgba(244,63,94,.55); color:#fda4b4; background:rgba(244,63,94,.08); }
.badge.dept{ border-color:rgba(79,124,255,.4); color:#a9c0ff; background:var(--accent-soft); }

/* حقل الإدخال */
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"]{ background:transparent; }
[data-testid="stChatInput"], [data-testid="stChatInput"] > div{
  background:var(--panel) !important; border-color:var(--line) !important; border-radius:14px;
}
[data-testid="stChatInput"]:focus-within{ border-color:var(--accent) !important; box-shadow:0 0 0 3px rgba(79,124,255,.18); }
[data-testid="stChatInput"] textarea{ background:transparent !important; color:var(--text); }
[data-testid="stChatInputSubmitButton"]{ background:var(--accent) !important; color:#fff !important; border-radius:10px; }

/* الحقول والنماذج */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div{
  background:var(--field) !important; border-color:var(--line) !important; border-radius:10px !important;
}
[data-baseweb="input"]:focus-within{ border-color:var(--accent) !important; box-shadow:0 0 0 3px rgba(79,124,255,.18); }
[data-testid="stForm"]{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:1.2rem; }
div[data-testid="stVerticalBlockBorderWrapper"]{ border-radius:16px; }
[data-testid="stMetric"]{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px 16px; }
[data-testid="stMetricLabel"]{ color:var(--muted); }
[data-testid="stTabs"] button[aria-selected="true"]{ color:#fff; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"]{ background:var(--accent); }
[data-testid="stAlert"]{ border-radius:12px; }

/* الأزرار */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button{
  min-height:2.8rem; border-radius:12px; border:1px solid var(--line); background:var(--panel);
  color:var(--text); font-weight:600; transition:.18s;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover{
  border-color:var(--accent); background:var(--panel-2); color:#fff; transform:translateY(-1px); box-shadow:0 8px 24px rgba(0,0,0,.25);
}
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]{
  background:var(--accent) !important; border-color:var(--accent) !important; color:#fff !important;
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover{
  background:#6b92ff !important;
}
hr{ border-color:var(--line) !important; }
</style>
"""