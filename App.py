"""Radd — مساعد الدعم الذكي: تسجيل دخول، محادثات محفوظة لكل مستخدم، ولوحة إدارة."""
from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel

import auth
import database as dbm
from database import DEPARTMENTS, PRIORITIES, STATUS_AI, STATUS_CLOSED, STATUS_ESCALATED, STATUS_PROGRESS, STATUSES
from style import CSS

log = logging.getLogger("radd")

# ───────────────────────── الإعدادات ─────────────────────────
DEFAULT_MODEL = "gemini-3.6-flash"  # يمكن تغييره من secrets.toml عبر GEMINI_MODEL
RATE_LIMIT = 8  # أقصى عدد رسائل للمستخدم في الدقيقة
SYSTEM_PROMPT = f"""أنت Radd، مساعد دعم فني لشركة تقنية.
- أجب دائماً بالعربية بأسلوب مهذب ومباشر، وقدّم خطوات حل واضحة ومرتبة.
- إذا كان السؤال ناقصاً فاطلب التفاصيل التي تحتاجها بسؤال واحد قصير.
- لا تختلق معلومات؛ وإن لم تكن متأكداً فاقترح تحويل الطلب إلى موظف بشري.
أعد الإجابة بصيغة JSON فقط بالحقول: reply (نص الرد)، department (واحد من: {"، ".join(DEPARTMENTS)})،
priority (واحد من: {"، ".join(PRIORITIES)}) حسب خطورة المشكلة وإلحاحها."""

SUGGESTIONS = [
    "كيف أستعيد كلمة المرور؟",
    "التطبيق يتوقف عند فتحه",
    "أرغب في استرداد مبلغ دفعته",
    "أحتاج مساعدة في إعداد حسابي",
]

st.set_page_config(page_title="Radd", page_icon="💬", layout="wide")


def get_secret(name: str, default: str | None = None) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value or os.getenv(name) or default


@st.cache_resource
def setup() -> bool:
    dbm.init_db()
    email, password = get_secret("ADMIN_EMAIL"), get_secret("ADMIN_PASSWORD")
    if email and password:
        try:
            auth.ensure_admin(email, password)
        except ValueError as exc:
            log.warning("إعداد المدير: %s", exc)
    else:
        log.warning("ADMIN_EMAIL / ADMIN_PASSWORD غير موجودين: لن يوجد حساب مدير.")
    return True


# ───────────────────────── الذكاء الاصطناعي ─────────────────────────
class TicketReply(BaseModel):
    reply: str
    department: str
    priority: str


@st.cache_resource
def get_client():
    key = get_secret("GEMINI_API_KEY")
    return genai.Client(api_key=key) if key else None


def ask_ai(history: list[dict]) -> dict:
    """يرسل آخر 12 رسالة ويعيد الرد مع القسم والأولوية."""
    client = get_client()
    if client is None:
        raise RuntimeError("مفتاح GEMINI_API_KEY غير موجود في .streamlit/secrets.toml")
    contents = [
        types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part(text=m["content"])])
        for m in history[-12:]
    ]
    response = client.models.generate_content(
        model=get_secret("GEMINI_MODEL", DEFAULT_MODEL),
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, response_mime_type="application/json",
            response_schema=TicketReply, temperature=0.6,
        ),
    )
    try:
        data = json.loads(response.text)
        if not isinstance(data, dict):
            data = {"reply": response.text}
    except (TypeError, ValueError):
        data = {"reply": response.text or ""}
    reply = str(data.get("reply") or "").strip()
    if not reply:
        raise RuntimeError("وصل رد فارغ من النموذج")
    dept, priority = data.get("department"), data.get("priority")
    return {
        "reply": reply,
        "department": dept if dept in DEPARTMENTS else "دعم فني",
        "priority": priority if priority in PRIORITIES else "متوسطة",
    }


# ───────────────────────── الجلسة ─────────────────────────
def current_user() -> dict | None:
    ss = st.session_state
    if ss.get("user"):
        fresh = auth.get_user(ss.user["id"])  # يلتقط الإيقاف أو تغيّر الصلاحية فوراً
        if fresh and fresh["is_active"]:
            ss.user = fresh
            return fresh
        ss.clear()
        return None
    token = st.query_params.get("s")
    if token:
        user = auth.user_from_token(token)
        if user:
            ss.user = user
            return user
        del st.query_params["s"]
    return None


def start_session(user: dict, remember: bool = False) -> None:
    st.session_state.user = user
    st.session_state.page = "chat"
    st.session_state.conv_id = None
    if remember:
        st.query_params["s"] = auth.create_session(user["id"])
    st.rerun()


def logout() -> None:
    token = st.query_params.get("s")
    if token:
        auth.revoke_session(token)
        del st.query_params["s"]
    st.session_state.clear()
    st.rerun()


# ───────────────────────── صفحة الدخول ─────────────────────────
def login_page() -> None:
    st.markdown(
        "<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
        "[data-testid='stExpandSidebarButton']{display:none}.block-container{max-width:460px}</style>"
        '<div class="auth-brand"><b>Radd</b><span>مساعد الدعم الذكي</span></div>',
        unsafe_allow_html=True,
    )
    tab_in, tab_up = st.tabs(["تسجيل الدخول", "إنشاء حساب"])

    with tab_in:
        with st.form("login"):
            email = st.text_input("البريد الإلكتروني", placeholder="name@example.com")
            password = st.text_input("كلمة المرور", type="password")
            remember = st.checkbox(
                "تذكّرني على هذا الجهاز", value=True,
                help="يُحفظ رمز الدخول في رابط الصفحة لمدة 7 أيام. لا تشارك الرابط مع أحد.",
            )
            submitted = st.form_submit_button("تسجيل الدخول", type="primary", width="stretch")
        if submitted:
            if not email or not password:
                st.error("أدخل البريد الإلكتروني وكلمة المرور.")
            else:
                user, error = auth.authenticate(email, password)
                if error:
                    st.error(error)
                else:
                    start_session(user, remember)

    with tab_up:
        with st.form("signup"):
            name = st.text_input("الاسم")
            email = st.text_input("البريد الإلكتروني", placeholder="name@example.com", key="su_email")
            password = st.text_input("كلمة المرور", type="password", key="su_pw",
                                     help="8 أحرف على الأقل، وتحتوي على حروف وأرقام.")
            confirm = st.text_input("تأكيد كلمة المرور", type="password")
            st.caption("بإنشاء حساب، توافق على أن يراجع فريق الدعم طلباتك ومحادثاتك لمساعدتك.")
            submitted = st.form_submit_button("إنشاء الحساب", type="primary", width="stretch")
        if submitted:
            if password != confirm:
                st.error("كلمتا المرور غير متطابقتين.")
            else:
                user, error = auth.register(name, email, password)
                if error:
                    st.error(error)
                else:
                    start_session(user)

    st.markdown('<div class="footer">© 2026 Radd · جميع الحقوق محفوظة</div>', unsafe_allow_html=True)


# ───────────────────────── الشريط الجانبي ─────────────────────────
def go(page: str) -> None:
    st.session_state.page = page


def open_conversation(conv_id: int) -> None:
    st.session_state.page = "chat"
    st.session_state.conv_id = conv_id


def sidebar(user: dict) -> None:
    ss = st.session_state
    with st.sidebar:
        st.markdown('<div class="brand"><b>Radd</b><small>مساعد الدعم الذكي</small></div>', unsafe_allow_html=True)
        role_chip = '<span class="chip">مدير</span>' if user["role"] == "admin" else ""
        st.markdown(
            f'<div class="usercard"><div class="avatar">{html.escape(user["name"][:1].upper())}</div>'
            f'<div class="uinfo"><b>{html.escape(user["name"])}</b><small>{html.escape(user["email"])}</small></div>'
            f"{role_chip}</div>",
            unsafe_allow_html=True,
        )
        st.button("محادثة جديدة", icon=":material/add:", type="primary", width="stretch",
                  on_click=lambda: ss.update(page="chat", conv_id=None))

        page = ss.get("page", "chat")
        nav = [("account", "حسابي", ":material/account_circle:")]
        if user["role"] == "admin":
            nav.insert(0, ("admin", "لوحة الإدارة", ":material/admin_panel_settings:"))
        for key, label, icon in nav:
            st.button(label, icon=icon, key=f"{'conva' if page == key else 'conv'}_nav_{key}",
                      width="stretch", on_click=go, args=(key,))

        st.markdown('<div class="side-label">محادثاتي</div>', unsafe_allow_html=True)
        convs = dbm.list_conversations(user["id"])
        with st.container(height=230, border=False):
            if not convs:
                st.caption("لا توجد محادثات بعد.")
            for c in convs:
                active = ss.get("page") == "chat" and ss.get("conv_id") == c["id"]
                title = c["title"] if len(c["title"]) <= 30 else c["title"][:29] + "…"
                st.button(title, key=f"{'conva' if active else 'conv'}_{c['id']}", width="stretch",
                          on_click=open_conversation, args=(c["id"],))

        st.divider()
        if st.button("تسجيل الخروج", icon=":material/logout:", width="stretch"):
            logout()

        online = get_client() is not None
        st.markdown(
            f'<div class="status" style="margin-top:1rem"><span class="dot{"" if online else " off"}"></span>'
            f'{"الخدمة متصلة" if online else "مفتاح API غير موجود"}</div>',
            unsafe_allow_html=True,
        )


# ───────────────────────── صفحة المحادثة ─────────────────────────
AVATARS = {"user": ":material/person:", "assistant": ":material/support_agent:"}


def badges(meta: dict) -> str:
    hi = " hi" if meta["priority"] == "عالية" else ""
    return (f'<span class="badge dept">{html.escape(meta["department"])}</span>'
            f'<span class="badge{hi}">الأولوية: {html.escape(meta["priority"])}</span>')


def export_text(title: str, messages: list[dict]) -> str:
    lines = [f"Radd — {title}", "=" * 40, ""]
    for m in messages:
        who = "أنا" if m["role"] == "user" else "Radd"
        lines += [f"[{m['created_at']}] {who}:", m["content"], ""]
    return "\n".join(lines)


def render_hero() -> None:
    st.markdown(
        '<div class="hero">'
        '<span class="hero-kicker">Radd · مساعد الدعم الذكي</span>'
        '<h1 class="hero-title">كيف يمكننا مساعدتك اليوم؟</h1>'
        '<p class="hero-note">اكتب سؤالك وسيصلك الرد فوراً. يفهم Radd مشكلتك، ويرتّب طلبك '
        "حسب القسم والأولوية، ويحوّله إلى موظف بشري عندما تحتاج.</p></div>",
        unsafe_allow_html=True,
    )


def handle_prompt(user: dict, prompt: str) -> str | None:
    """يحفظ الرسالة ويطلب الرد. يعيد نص الخطأ إن فشل."""
    ss = st.session_state
    prompt = prompt.strip()
    if not prompt:
        return None
    if dbm.count_recent_user_messages(user["id"], 60) >= RATE_LIMIT:
        return "أرسلت رسائل كثيرة خلال وقت قصير. انتظر دقيقة ثم أعد المحاولة."
    conv_id, created = ss.get("conv_id"), False
    if not conv_id:
        conv_id, created = dbm.create_conversation(user["id"], " ".join(prompt.split())[:60]), True
    ss.conv_id = conv_id
    msg_id = dbm.add_message(conv_id, "user", prompt)
    try:
        with st.spinner("Radd يكتب الرد..."):
            result = ask_ai(dbm.get_messages(conv_id))
    except Exception as exc:  # noqa: BLE001
        log.exception("فشل طلب الذكاء الاصطناعي")
        dbm.delete_message(msg_id)
        if created:
            dbm.delete_conversation(user["id"], conv_id)
            ss.conv_id = None
        detail = f" ({exc})" if user["role"] == "admin" else ""
        return f"تعذّر الحصول على رد حالياً. حاول مرة أخرى بعد قليل.{detail}"
    ticket_id = dbm.save_ticket(user["id"], conv_id, prompt, result["reply"],
                                result["department"], result["priority"], STATUS_AI)
    dbm.add_message(conv_id, "assistant", result["reply"], result["department"], result["priority"], ticket_id)
    return None


def chat_page(user: dict) -> None:
    ss = st.session_state
    st.markdown("<style>.block-container{max-width:880px}</style>", unsafe_allow_html=True)

    if ss.get("conv_id") and not dbm.get_conversation(user["id"], ss.conv_id):
        ss.conv_id = None  # محادثة محذوفة أو لا تخصّ هذا المستخدم

    prompt = st.chat_input("اكتب رسالتك إلى Radd...", max_chars=2000) or ss.pop("pending", None)
    error = handle_prompt(user, prompt) if prompt else None

    conv_id = ss.get("conv_id")
    messages = dbm.get_messages(conv_id) if conv_id else []
    conv = dbm.get_conversation(user["id"], conv_id) if conv_id else None

    if conv:
        c1, c2, c3 = st.columns([6, 1.6, 1.6], vertical_alignment="center")
        c1.markdown(f'<p class="topbar-title">{html.escape(conv["title"])}</p>'
                    f'<span class="topbar-sub">آخر نشاط: {conv["updated_at"]}</span>', unsafe_allow_html=True)
        c2.download_button("تصدير", data=export_text(conv["title"], messages), file_name=f"radd-{conv_id}.txt",
                           mime="text/plain", icon=":material/download:", width="stretch")
        with c3.popover("حذف", icon=":material/delete:"):
            st.write("حذف هذه المحادثة نهائياً؟")
            if st.button("تأكيد الحذف", type="primary", key="confirm_delete"):
                dbm.delete_conversation(user["id"], conv_id)
                ss.conv_id = None
                st.toast("تم حذف المحادثة")
                st.rerun()
        st.divider()
    else:
        render_hero()

    if error:
        st.error(error)

    for msg in messages:
        with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
            st.markdown(msg["content"])
            if msg["meta"]:
                st.markdown(badges(msg["meta"]), unsafe_allow_html=True)

    if not messages:
        st.markdown('<div class="sg-label">جرّب أحد هذه الأسئلة</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, text in enumerate(SUGGESTIONS):
            cols[i % 2].button(text, key=f"sg{i}", width="stretch",
                               on_click=lambda t=text: ss.update(pending=t))
        return

    last = next((m for m in reversed(messages) if m["ticket_id"]), None)
    if last:
        status = dbm.get_ticket_status(last["ticket_id"])
        if status in (STATUS_ESCALATED, STATUS_PROGRESS):
            st.success("تم تحويل طلبك إلى فريق الدعم البشري، وسيتواصل معك قريباً.")
        elif status == STATUS_AI and st.button("تحويل إلى موظف بشري", key="escalate", icon=":material/support_agent:"):
            dbm.escalate_ticket(last["ticket_id"], user["id"])
            st.rerun()


# ───────────────────────── صفحة الحساب ─────────────────────────
def bar(data: dict, height: int, horizontal: bool = False) -> None:
    if data:
        st.bar_chart(pd.Series(data, name="التذاكر"), height=height, color="#4f7cff", horizontal=horizontal)
    else:
        st.caption("لا توجد بيانات بعد.")


def page_header(title: str, sub: str) -> None:
    st.markdown(f'<p class="page-title">{title}</p><p class="page-sub">{sub}</p>', unsafe_allow_html=True)


def account_page(user: dict) -> None:
    st.markdown("<style>.block-container{max-width:760px}</style>", unsafe_allow_html=True)
    page_header("حسابي", "إدارة بياناتك الشخصية وأمان حسابك.")

    with st.container(border=True):
        st.markdown("**معلومات الحساب**")
        st.caption(f"البريد الإلكتروني: {user['email']}  ·  تاريخ الانضمام: {user['created_at'] or '—'}")
        with st.form("profile"):
            name = st.text_input("الاسم", value=user["name"])
            if st.form_submit_button("حفظ التغييرات", type="primary"):
                err = auth.update_name(user["id"], name)
                if err:
                    st.error(err)
                else:
                    st.toast("تم حفظ الاسم")
                    st.rerun()

    with st.container(border=True):
        st.markdown("**تغيير كلمة المرور**")
        with st.form("password"):
            current = st.text_input("كلمة المرور الحالية", type="password")
            new = st.text_input("كلمة المرور الجديدة", type="password", help="8 أحرف على الأقل، حروف وأرقام.")
            confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
            if st.form_submit_button("تغيير كلمة المرور", type="primary"):
                if new != confirm:
                    st.error("كلمتا المرور غير متطابقتين.")
                elif err := auth.change_password(user["id"], current, new):
                    st.error(err)
                else:
                    if "s" in st.query_params:
                        del st.query_params["s"]
                    st.success("تم تغيير كلمة المرور، وسيُطلب منك تسجيل الدخول على باقي الأجهزة.")

    with st.expander("منطقة الخطر"):
        st.write("حذف جميع محادثاتك. لا يمكن التراجع عن ذلك.")
        if st.button("حذف جميع محادثاتي", key="wipe"):
            dbm.delete_all_conversations(user["id"])
            st.session_state.conv_id = None
            st.toast("تم حذف جميع المحادثات")
            st.rerun()
        if user["role"] != "admin":
            st.divider()
            st.write("حذف حسابك وجميع بياناتك نهائياً.")
            pw = st.text_input("أدخل كلمة المرور للتأكيد", type="password", key="del_pw")
            if st.button("حذف حسابي نهائياً", type="primary", key="del_acc"):
                err = auth.delete_account(user["id"], pw)
                if err:
                    st.error(err)
                else:
                    logout()


# ───────────────────────── لوحة الإدارة ─────────────────────────
def admin_page(user: dict) -> None:
    if user["role"] != "admin":  # حماية من جهة الخادم
        st.error("غير مصرّح لك بالدخول إلى هذه الصفحة.")
        return
    st.markdown("<style>.block-container{max-width:1200px}</style>", unsafe_allow_html=True)
    page_header("لوحة الإدارة", "نظرة عامة على الطلبات والمستخدمين.")
    tab_over, tab_tickets, tab_convs, tab_users = st.tabs(["نظرة عامة", "التذاكر", "المحادثات", "المستخدمون"])

    with tab_over:
        s = dbm.overview_stats()
        cols = st.columns(6)
        for col, (label, key) in zip(cols, [("المستخدمون", "users"), ("المحادثات", "conversations"),
                                            ("التذاكر", "tickets"), ("تذاكر اليوم", "today"),
                                            ("بانتظار موظف", "escalated"), ("مغلقة", "closed")]):
            col.metric(label, s[key])
        days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(13, -1, -1)]
        per_day = dbm.tickets_per_day(14)
        c1, c2 = st.columns(2)
        with c1, st.container(border=True):
            st.markdown("**التذاكر خلال آخر 14 يوماً**")
            bar({d[5:]: per_day.get(d, 0) for d in days}, 260)
        with c2, st.container(border=True):
            st.markdown("**التذاكر حسب القسم**")
            bar(dbm.count_by("department"), 260, horizontal=True)
        c3, c4 = st.columns(2)
        with c3, st.container(border=True):
            st.markdown("**حسب الأولوية**")
            bar(dbm.count_by("priority"), 220, horizontal=True)
        with c4, st.container(border=True):
            st.markdown("**حسب الحالة**")
            bar(dbm.count_by("status"), 220, horizontal=True)

    with tab_tickets:
        df = pd.DataFrame(dbm.all_tickets())
        if df.empty:
            st.info("لا توجد تذاكر بعد.")
        else:
            only_open = st.toggle("عرض المصعّدة لموظف فقط (تنتظر مراجعة)")
            f1, f2, f3, f4 = st.columns([2, 2, 2, 3])
            status = f1.multiselect("الحالة", STATUSES)
            dept = f2.multiselect("القسم", DEPARTMENTS)
            prio = f3.multiselect("الأولوية", PRIORITIES)
            search = f4.text_input("بحث في نص الطلب أو البريد")
            if only_open:
                df = df[df["status"] == STATUS_ESCALATED]
            if status:
                df = df[df["status"].isin(status)]
            if dept:
                df = df[df["department"].isin(dept)]
            if prio:
                df = df[df["priority"].isin(prio)]
            if search:
                mask = df["user_query"].fillna("").str.contains(search, case=False, regex=False) | \
                    df["user_email"].str.contains(search, case=False, regex=False)
                df = df[mask]

            view = df[["id", "created_at", "user_email", "department", "priority", "status", "user_query"]].rename(columns={
                "id": "#", "created_at": "التاريخ", "user_email": "المستخدم", "department": "القسم",
                "priority": "الأولوية", "status": "الحالة", "user_query": "الطلب"})
            st.caption(f"{len(view)} تذكرة")
            st.dataframe(view, hide_index=True, width="stretch", height=320)
            st.download_button("تصدير CSV", data=view.to_csv(index=False).encode("utf-8-sig"),
                               file_name="tickets.csv", mime="text/csv", icon=":material/download:")

            if len(df):
                st.markdown("**تحديث تذكرة**")
                tid = st.selectbox("رقم التذكرة", df["id"].tolist(), format_func=lambda i: f"#{i}")
                row = df[df["id"] == tid].iloc[0]
                with st.container(border=True):
                    st.markdown(f"**الطلب:** {row['user_query']}")
                    st.markdown(f"**رد المساعد:** {row['ai_response']}")
                new_status = st.selectbox("الحالة الجديدة", STATUSES, index=STATUSES.index(row["status"])
                                          if row["status"] in STATUSES else 0)
                if st.button("حفظ الحالة", type="primary"):
                    dbm.update_ticket_status(int(tid), new_status)
                    st.toast("تم تحديث التذكرة")
                    st.rerun()

    with tab_convs:
        convs = pd.DataFrame(dbm.admin_conversations())
        if convs.empty:
            st.info("لا توجد محادثات بعد.")
        else:
            q = st.text_input("بحث بالبريد أو الاسم أو عنوان المحادثة", key="conv_search")
            if q:
                mask = (convs["email"].str.contains(q, case=False, regex=False)
                        | convs["name"].str.contains(q, case=False, regex=False)
                        | convs["title"].str.contains(q, case=False, regex=False))
                convs = convs[mask]
            st.caption(f"{len(convs)} محادثة")
            if len(convs):
                st.dataframe(
                    convs[["id", "email", "name", "title", "messages", "updated_at"]].rename(columns={
                        "id": "#", "email": "البريد", "name": "الاسم", "title": "العنوان",
                        "messages": "الرسائل", "updated_at": "آخر نشاط"}),
                    hide_index=True, width="stretch", height=260)
                cid = st.selectbox("افتح محادثة", convs["id"].tolist(), format_func=lambda i: (
                    f"#{i} — {convs.loc[convs['id'] == i, 'email'].iloc[0]} — "
                    f"{convs.loc[convs['id'] == i, 'title'].iloc[0]}"))
                with st.container(border=True):
                    for m in dbm.get_messages(int(cid)):
                        with st.chat_message(m["role"], avatar=AVATARS[m["role"]]):
                            st.markdown(m["content"])
                            if m["meta"]:
                                st.markdown(badges(m["meta"]), unsafe_allow_html=True)

    with tab_users:
        users = pd.DataFrame(dbm.all_users())
        view = users.assign(role=users["role"].map({"admin": "مدير", "user": "مستخدم"}),
                            is_active=users["is_active"].map({1: "نشط", 0: "موقوف"}))
        view = view[["id", "name", "email", "role", "is_active", "conversations", "created_at", "last_login"]].rename(columns={
            "id": "#", "name": "الاسم", "email": "البريد", "role": "الدور", "is_active": "الحالة",
            "conversations": "المحادثات", "created_at": "تاريخ التسجيل", "last_login": "آخر دخول"})
        st.dataframe(view, hide_index=True, width="stretch")

        regular = users[users["role"] == "user"]
        if regular.empty:
            st.info("لا يوجد مستخدمون مسجّلون بعد.")
        else:
            st.markdown("**إدارة مستخدم**")
            uid = st.selectbox("المستخدم", regular["id"].tolist(),
                               format_func=lambda i: regular.loc[regular["id"] == i, "email"].iloc[0])
            active = bool(regular.loc[regular["id"] == uid, "is_active"].iloc[0])
            b1, b2 = st.columns(2)
            if b1.button("إيقاف الحساب" if active else "تفعيل الحساب", width="stretch"):
                auth.set_active(int(uid), not active)
                st.toast("تم تحديث الحساب")
                st.rerun()
            if b2.button("إنشاء كلمة مرور مؤقتة", width="stretch"):
                temp = auth.admin_reset_password(int(uid))
                st.warning("انسخ كلمة المرور المؤقتة الآن؛ لن تظهر مرة أخرى. أرسلها للمستخدم وسيغيّرها بعد الدخول.")
                st.code(temp, language=None)


# ───────────────────────── التشغيل ─────────────────────────
setup()
st.markdown(CSS, unsafe_allow_html=True)
current = current_user()
if current is None:
    login_page()
    st.stop()

sidebar(current)
page = st.session_state.get("page", "chat")
if page == "admin":
    admin_page(current)
elif page == "account":
    account_page(current)
else:
    chat_page(current)