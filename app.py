import streamlit as st
import subprocess
import sys
import os

st.set_page_config(
    page_title="AI News Aggregator",
    page_icon="📰",
    layout="centered"
)

# Minimal CSS — only layout touches, no color overrides
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.title("📰 AI News Aggregator")
st.caption("Daily digest of AI breakthroughs, Anthropic updates & YouTube highlights — straight to your inbox.")
st.divider()

# ── Credentials ───────────────────────────────────────────────────────────────
st.subheader("🔑 Credentials")
api_key = st.text_input("Resend API key", type="password", placeholder="re_xxxxxxxxxxxxxxxxxxxxxxxx")
email   = st.text_input("Your email address", placeholder="you@gmail.com")

st.divider()

# ── Settings ──────────────────────────────────────────────────────────────────
st.subheader("⚙️ Settings")
col1, col2, col3 = st.columns(3)
with col1:
    scrape_window = st.selectbox("Scrape window", [24, 48, 72, 168], format_func=lambda h: f"Last {h}h")
with col2:
    top_n = st.selectbox("Top articles", [5, 10, 15, 20], index=1)
with col3:
    interval_label = st.selectbox("Repeat every", ["2 minutes", "6 hours", "12 hours", "24 hours", "48 hours"], index=3)

interval_map = {"2 minutes": 2, "6 hours": 360, "12 hours": 720, "24 hours": 1440, "48 hours": 2880}
interval_minutes = interval_map[interval_label]

st.divider()

# ── Validation ────────────────────────────────────────────────────────────────
ready = bool(api_key and api_key.startswith("re_") and email and "@" in email)
if api_key and not api_key.startswith("re_"):
    st.warning("API key should start with `re_`")
if email and "@" not in email:
    st.warning("Enter a valid email address")

# ── Actions ───────────────────────────────────────────────────────────────────
st.subheader("⚡ Actions")
col_a, col_b = st.columns(2)

with col_a:
    if st.button("🚀 Send now", disabled=not ready, use_container_width=True):
        env = os.environ.copy()
        env["RESEND_API_KEY"]      = api_key
        env["MY_EMAIL"]            = email
        env["PIPELINE_HOURS"]      = str(scrape_window)
        env["PIPELINE_TOP_N"]      = str(top_n)

        with st.spinner("Running pipeline..."):
            result = subprocess.run(
                [sys.executable, "-m", "app.services.process_email"],
                capture_output=True, text=True, env=env
            )

        if result.returncode == 0:
            st.success("✅ Digest sent! Check your inbox.")
        else:
            st.error("❌ Pipeline failed. See logs below.")

        with st.expander("Logs"):
            st.code((result.stdout + result.stderr).strip(), language="text")

with col_b:
    scheduler_running = st.session_state.get("scheduler_pid") is not None

    if not scheduler_running:
        if st.button("🕐 Start scheduler", disabled=not ready, use_container_width=True):
            env = os.environ.copy()
            env["RESEND_API_KEY"]         = api_key
            env["MY_EMAIL"]               = email
            env["PIPELINE_HOURS"]         = str(scrape_window)
            env["PIPELINE_TOP_N"]         = str(top_n)
            env["SCHEDULER_INTERVAL_MIN"] = str(interval_minutes)

            proc = subprocess.Popen(
                [sys.executable, "runner_daily.py"],
                env=env,
                stdout=open("scheduler.log", "w"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            st.session_state["scheduler_pid"]      = proc.pid
            st.session_state["scheduler_proc"]     = proc
            st.session_state["scheduler_email"]    = email
            st.session_state["scheduler_interval"] = interval_label
            st.rerun()
    else:
        if st.button("⛔ Stop scheduler", use_container_width=True):
            proc = st.session_state.get("scheduler_proc")
            if proc:
                proc.terminate()
            for k in ["scheduler_pid", "scheduler_proc", "scheduler_email", "scheduler_interval"]:
                st.session_state.pop(k, None)
            st.rerun()

# ── Scheduler status ──────────────────────────────────────────────────────────
if st.session_state.get("scheduler_pid"):
    proc  = st.session_state.get("scheduler_proc")
    alive = proc and proc.poll() is None

    if alive:
        st.success(
            f"🟢 Scheduler running (PID {st.session_state['scheduler_pid']}) — "
            f"sending to **{st.session_state.get('scheduler_email','')}** "
            f"every **{st.session_state.get('scheduler_interval','')}**"
        )
        st.info("Closing this tab is fine. Sleeping your laptop will pause the scheduler.")

        with st.expander("📄 Scheduler log"):
            try:
                log = open("scheduler.log").read()
                st.code(log[-3000:], language="text")
            except FileNotFoundError:
                st.caption("No log yet.")
    else:
        st.warning("Scheduler ended unexpectedly. Check scheduler.log.")
        for k in ["scheduler_pid", "scheduler_proc"]:
            st.session_state.pop(k, None)

st.divider()
st.caption("Powered by Resend · APScheduler · Streamlit")