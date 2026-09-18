import os
import sqlite3
import pandas as pd
import streamlit as st
from google import genai

# --- 1. إعدادات الصفحة والتصميم ---
st.set_page_config(
    page_title="نظام الدعم الفني والتحليلات الذكي",
    page_icon="🤖",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    * { font-family: 'Cairo', sans-serif !important; }
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #f8fafc; }
    div[data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 18px;
        backdrop-filter: blur(10px);
    }
    .stButton > button { border-radius: 12px !important; font-weight: 700 !important; }
    .stTextArea textarea { border-radius: 12px !important; background-color: #1e293b !important; color: #f8fafc !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. إعداد قاعدة البيانات الهيكلية ---
def init_db():
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_query TEXT,
            ai_response TEXT,
            department TEXT,
            priority TEXT,
            status TEXT DEFAULT 'مكتملة بالذكاء الاصطناعي'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- 3. إعداد عميل الذكاء الاصطناعي ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# --- 4. الواجهة الرئيسية ---
st.sidebar.title("📌 لوحة التحكّم")
page = st.sidebar.radio("انتقل إلى:", ["🤖 الدعم الفني الذكي", "📈 تحليلات الإدارة الحية"])

if page == "🤖 الدعم الفني الذكي":
    st.title("🤖 نظام الدعم الفني والخدمة الذكية")
    st.write("أهلاً بك. كيف يمكننا مساعدتك اليوم؟")
    
    user_input = st.text_area("اكتب سؤالك أو شكواك هنا:", height=120)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("✨ توليد الرد بالذكاء الاصطناعي", type="primary", use_container_width=True):
            if user_input.strip():
                if client:
                    try:
                        # صياغة واضحة وبسيطة لتجنب أخطاء النصوص
                        system_instruction = "أنت ممثل دعم فني احترافي لشركة تقنية. أجب دائماً باللغة العربية بأسلوب مهذب ومباشر وتقديم حلول تقنية مفيدة."
                        
                        response = client.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=f"{system_instruction}\n\nطلب العميل: {user_input}"
                        )
                        
                        reply = response.text
                        dept = "دعم فني"
                        priority = "متوسطة"

                        st.success("تم توليد الرد بنجاح:")
                        st.write(reply)
                        
                        # حفظ البيانات في قاعدة البيانات
                        conn = sqlite3.connect("tickets.db")
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO tickets (user_query, ai_response, department, priority, status) VALUES (?, ?, ?, ?, ?)",
                            (user_input, reply, dept, priority, "مكتملة بالذكاء الاصطناعي")
                        )
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء الاتصال بالخدمة: {e}")
                else:
                    st.error("مفتاح API غير متوفر.")
            else:
                st.warning("يرجى كتابة نص السؤال أولاً.")
                
    with col2:
        if st.button("⚠️ تصعيد الطلب لموظف بشري", use_container_width=True):
            if user_input.strip():
                conn = sqlite3.connect("tickets.db")
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO tickets (user_query, ai_response, department, priority, status) VALUES (?, ?, ?, ?, ?)",
                    (user_input, "تحت المراجعة البشرية", "دعم عام", "عالية", "مصعدة لموظف بشري")
                )
                conn.commit()
                conn.close()
                st.warning("تم تصعيد التذكرة بنجاح إلى قسم خدمة العملاء البشري للتعامل الفوري.")
            else:
                st.warning("يرجى كتابة نص الشكوى أولاً لتصعيدها.")

elif page == "📈 تحليلات الإدارة الحية":
    st.title("📈 لوحة تحكم الإدارة والتحليلات الحية")
    
    conn = sqlite3.connect("tickets.db")
    df_tickets = pd.read_sql_query("SELECT * FROM tickets", conn)
    conn.close()
    
    if not df_tickets.empty:
        total_tickets = len(df_tickets)
        ai_resolved = len(df_tickets[df_tickets["status"] == "مكتملة بالذكاء الاصطناعي"])
        escalated = len(df_tickets[df_tickets["status"] == "مصعدة لموظف بشري"])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("إجمالي التذاكر", total_tickets)
        m2.metric("حُلّت بالذكاء الاصطناعي", ai_resolved)
        m3.metric("تصعيد بشري", escalated)
        
        st.markdown("---")
        st.subheader("سجل التذاكر المخزنة")
        st.dataframe(df_tickets, use_container_width=True)
    else:
        st.info("لا توجد تذاكر مسجلة في قاعدة البيانات حالياً.")