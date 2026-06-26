from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone, timedelta
import resend
import os

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
EMAIL_TO     = os.environ.get("DIGEST_EMAIL_TO", "")
EMAIL_FROM   = os.environ.get("DIGEST_EMAIL_FROM", "DealerHunters Signals <signals@mpshunters.com>")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing Supabase credentials")

resend.api_key = os.environ.get("RESEND_API_KEY", "")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

now      = datetime.now(timezone.utc)
week_ago = (now - timedelta(days=7)).isoformat()
week_label = (now - timedelta(days=7)).strftime("%B %-d, %Y")

opps = supabase.table("opportunities").select("*").gte("created_at", week_ago).execute()
data = opps.data or []

if not data:
    print("No opportunities this week — skipping weekly report.")
    raise SystemExit(0)

total_signals = len(data)
hot_leads     = sum(1 for d in data if d.get("is_hot_lead"))
contacted     = sum(1 for d in data if d.get("status") == "contacted")
won           = sum(1 for d in data if d.get("status") == "won")
ownership_cnt = sum(1 for d in data if (d.get("signal_type") or d.get("opportunity_type") or "")
                    in ("ownership_change", "Ownership Change"))

top5 = sorted(data, key=lambda d: d.get("confidence_score") or 0, reverse=True)[:5]

three_days_ago = (now - timedelta(days=3)).isoformat()
stale = [d for d in data
         if d.get("status") == "contacted"
         and (d.get("created_at") or "") <= three_days_ago]

week_of = f"Week of {week_label}"
subject  = f"DealerHunters Weekly Report — {week_of}"


def stat_row(label, value, color="#10B981"):
    return f"""
      <tr>
        <td style="padding:10px 0;color:#9CA3AF;font-size:13px;">{label}</td>
        <td style="padding:10px 0;text-align:right;font-weight:700;font-size:18px;color:{color};">{value}</td>
      </tr>"""


def opp_row(d, i):
    name  = d.get("dealership_name") or "Unnamed Dealership"
    city  = d.get("city") or ""
    state = d.get("state") or ""
    loc   = ", ".join(filter(None, [city, state])) or "—"
    sig   = (d.get("signal_type") or d.get("opportunity_type") or "Signal").replace("_", " ").title()
    score = d.get("confidence_score") or 0
    hot   = "🔥 " if d.get("is_hot_lead") else ""
    return f"""
      <tr style="border-bottom:1px solid #1F2937;">
        <td style="padding:10px 8px;color:#9CA3AF;font-size:12px;">{i}</td>
        <td style="padding:10px 8px;">
          <div style="font-weight:600;color:#F9FAFB;font-size:13px;">{hot}{name}</div>
          <div style="color:#6B7280;font-size:11px;margin-top:2px;">{loc}</div>
        </td>
        <td style="padding:10px 8px;color:#10B981;font-size:12px;">{sig}</td>
        <td style="padding:10px 8px;text-align:right;font-weight:700;color:#F9FAFB;font-size:14px;">{score}</td>
      </tr>"""


top5_rows = "".join(opp_row(d, i + 1) for i, d in enumerate(top5))

stale_items = ""
if stale:
    stale_items = f"""
    <div style="background:#1F2937;border-radius:10px;padding:18px 20px;margin-top:24px;">
      <div style="font-size:12px;font-weight:700;color:#9CA3AF;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;">
        Still Open — Contacted 3+ Days Ago
      </div>
      {''.join(f'<div style="color:#F9FAFB;font-size:13px;padding:5px 0;border-bottom:1px solid #374151;">{d.get("dealership_name","—")} <span style="color:#6B7280;font-size:11px;">· {(d.get("city") or "")} {(d.get("state") or "")}</span></div>' for d in stale)}
    </div>"""

html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0F172A;font-family:'Inter',system-ui,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0F172A;padding:32px 0;">
  <tr><td align="center">
    <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;">

      <!-- Header -->
      <tr><td style="background:#111827;border-radius:12px 12px 0 0;padding:24px 28px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="font-size:20px;font-weight:800;color:#fff;">
            <span style="color:#fff;">Dealer</span><span style="color:#10B981;">Hunters</span>
          </span>
          <span style="color:#6B7280;font-size:11px;margin-left:8px;">Weekly Intelligence Report</span>
        </div>
        <div style="color:#9CA3AF;font-size:13px;margin-top:6px;">{week_of}</div>
      </td></tr>

      <!-- Stats -->
      <tr><td style="background:#1A2236;padding:24px 28px;">
        <div style="font-size:11px;font-weight:700;color:#6B7280;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px;">
          This Week at a Glance
        </div>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1F2937;">
          {stat_row("Total signals detected", total_signals)}
          {stat_row("New opportunities", total_signals)}
          {stat_row("Hot leads", hot_leads, "#F97316")}
          {stat_row("Leads contacted", contacted, "#3B82F6")}
          {stat_row("Leads won", won, "#10B981")}
        </table>
      </td></tr>

      <!-- Top 5 -->
      <tr><td style="background:#111827;padding:24px 28px;">
        <div style="font-size:11px;font-weight:700;color:#6B7280;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:14px;">
          Top 5 Opportunities
        </div>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr style="border-bottom:1px solid #1F2937;">
            <th style="text-align:left;color:#6B7280;font-size:10px;padding:0 8px 8px;">#</th>
            <th style="text-align:left;color:#6B7280;font-size:10px;padding:0 8px 8px;">Dealership</th>
            <th style="text-align:left;color:#6B7280;font-size:10px;padding:0 8px 8px;">Signal</th>
            <th style="text-align:right;color:#6B7280;font-size:10px;padding:0 8px 8px;">Score</th>
          </tr>
          {top5_rows}
        </table>
        {stale_items}
      </td></tr>

      <!-- Closer -->
      <tr><td style="background:#065F46;border-radius:0 0 12px 12px;padding:22px 28px;">
        <div style="color:#D1FAE5;font-size:14px;font-weight:600;margin-bottom:8px;">
          {ownership_cnt} dealership{"s" if ownership_cnt != 1 else ""} changed ownership this week.
          How many did your team call?
        </div>
        <a href="https://dealerhunters.com/dashboard"
           style="display:inline-block;margin-top:10px;background:#10B981;color:#fff;
                  font-size:13px;font-weight:600;padding:10px 20px;border-radius:7px;
                  text-decoration:none;">
          View Dashboard →
        </a>
      </td></tr>

    </table>
    <p style="color:#374151;font-size:11px;margin-top:16px;text-align:center;">
      DealerHunters · True Measure Advisors, LLC
    </p>
  </td></tr>
</table>
</body>
</html>"""

result = resend.Emails.send({
    "from":    EMAIL_FROM,
    "to":      EMAIL_TO,
    "subject": subject,
    "html":    html,
})

print(f"Weekly report sent: {result}")
print(f"  {total_signals} signals | {hot_leads} hot | {won} won | {contacted} contacted")

try:
    supabase.table("digest_log").insert({
        "type":         "weekly_report",
        "sent_at":      now.isoformat(),
        "opp_count":    total_signals,
        "hot_count":    hot_leads,
        "email_to":     EMAIL_TO,
    }).execute()
except Exception:
    pass
