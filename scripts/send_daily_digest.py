from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime
import resend
import os

load_dotenv()

SUPABASE_URL      = os.environ.get("SUPABASE_URL")
SUPABASE_KEY      = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
RESEND_API_KEY    = os.environ.get("RESEND_API_KEY")
DIGEST_EMAIL_TO   = os.environ.get("DIGEST_EMAIL_TO")
DIGEST_EMAIL_FROM = os.environ.get("DIGEST_EMAIL_FROM", "DealerHunters <digest@dealerhunters.io>")
DASHBOARD_URL     = "https://dealerhunters-app.pages.dev/dashboard"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not RESEND_API_KEY:
    raise Exception("Missing RESEND_API_KEY")
if not DIGEST_EMAIL_TO:
    raise Exception("Missing DIGEST_EMAIL_TO")

resend.api_key = RESEND_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("DealerHunters daily digest starting...")

# ── Fetch new opportunities ────────────────────────────────────────────────
opps = supabase.table("opportunities") \
    .select("*") \
    .eq("status", "new") \
    .order("confidence_score", desc=True) \
    .execute().data or []

count = len(opps)
print(f"Found {count} new opportunities")

# ── Signal metadata ────────────────────────────────────────────────────────
SIGNAL_STYLES = {
    "ownership_change":  ("Ownership Change",  "#065F46", "#ECFDF5"),
    "hiring":            ("Marketing Hire",    "#1E40AF", "#EFF6FF"),
    "new_rooftop":       ("New Rooftop",       "#166534", "#F0FDF4"),
    "oem_event":         ("OEM Event",         "#6B21A8", "#FAF5FF"),
    "Ownership Change":  ("Ownership Change",  "#065F46", "#ECFDF5"),
    "Marketing Hire":    ("Marketing Hire",    "#1E40AF", "#EFF6FF"),
    "Leadership Change": ("Leadership Change", "#6B21A8", "#FAF5FF"),
    "Expansion":         ("Expansion",         "#166534", "#F0FDF4"),
}
DEFAULT_SIGNAL = ("Signal", "#344054", "#F2F4F7")


def signal_info(opp):
    raw = opp.get("signal_type") or opp.get("opportunity_type") or ""
    return SIGNAL_STYLES.get(raw, DEFAULT_SIGNAL)


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ── Email builders ─────────────────────────────────────────────────────────
def build_html(opportunities):
    today = datetime.utcnow().strftime("%B %d, %Y")
    n = len(opportunities)

    ownership  = sum(1 for o in opportunities if (o.get("signal_type") or o.get("opportunity_type") or "") in ("ownership_change", "Ownership Change"))
    hiring     = sum(1 for o in opportunities if (o.get("signal_type") or o.get("opportunity_type") or "") in ("hiring", "Marketing Hire"))
    leadership = sum(1 for o in opportunities if (o.get("signal_type") or o.get("opportunity_type") or "") in ("Leadership Change", "leadership_change"))
    raw_scores = [float(o.get("confidence_score") or o.get("fit_score") or 0) for o in opportunities if (o.get("confidence_score") or o.get("fit_score"))]
    avg_score  = round(sum(raw_scores) / len(raw_scores)) if raw_scores else 0

    cards = ""
    for opp in opportunities:
        label, color, bg = signal_info(opp)
        name     = esc(opp.get("dealership_name") or "Unnamed Dealership")
        city     = esc(opp.get("city") or "")
        state    = esc(opp.get("state") or "")
        location = f"{city}, {state}" if city and state else city or state or "Location unavailable"
        summary  = esc(opp.get("ai_summary") or "No summary available.")
        pitch    = esc(opp.get("pitch_angle") or opp.get("recommended_offer") or "")
        score    = int(opp.get("confidence_score") or opp.get("fit_score") or 0)
        phone    = opp.get("phone")
        website  = opp.get("website")

        pitch_block = ""
        if pitch:
            pitch_block = f"""
            <tr><td style="padding:12px 22px 0;">
              <div style="border-left:3px solid #10B981;background:#F0FDF9;padding:10px 14px;border-radius:0 8px 8px 0;">
                <div style="font-size:11px;font-weight:500;color:#9CA3AF;margin-bottom:3px;">Suggested pitch</div>
                <div style="font-size:13px;font-weight:500;color:#1A1F36;line-height:1.5;">{pitch}</div>
              </div>
            </td></tr>"""

        contact_row = ""
        if phone or website:
            phone_td = f'<td style="font-size:12px;color:#6B7280;padding-right:16px;">&#128222; {esc(phone)}</td>' if phone else ""
            web_td   = f'<td style="font-size:12px;"><a href="{esc(website)}" style="color:#10B981;text-decoration:none;">{esc(website)}</a></td>' if website else ""
            contact_row = f"""
            <tr><td style="padding:10px 22px 0;">
              <table border="0" cellpadding="0" cellspacing="0"><tr>{phone_td}{web_td}</tr></table>
            </td></tr>"""

        cards += f"""
        <table border="0" cellpadding="0" cellspacing="0" width="100%"
          style="background:#ffffff;border:1px solid #E8ECF4;border-top:3px solid #10B981;
                 border-radius:12px;margin-bottom:16px;">
          <tr>
            <td style="padding:20px 22px 0;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <div style="font-size:18px;font-weight:700;color:#1A1F36;line-height:1.25;">{name}</div>
                    <div style="font-size:13px;color:#9CA3AF;margin-top:4px;">{location}</div>
                  </td>
                  <td width="52" align="right" valign="top">
                    <div style="width:44px;height:44px;border-radius:50%;background:#F0FDF9;
                                border:2px solid #10B981;text-align:center;line-height:44px;
                                font-size:15px;font-weight:800;color:#10B981;">{score}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 22px 0;">
              <span style="display:inline-block;font-size:11px;font-weight:600;padding:3px 10px;
                           border-radius:999px;color:{color};background:{bg};letter-spacing:0.2px;">{label}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 22px 0;font-size:14px;line-height:1.65;color:#374151;">{summary}</td>
          </tr>
          {pitch_block}
          {contact_row}
          <tr>
            <td style="padding:16px 22px 20px;">
              <a href="{DASHBOARD_URL}"
                style="display:inline-block;background:#10B981;color:#ffffff;font-size:13px;
                       font-weight:600;padding:8px 18px;border-radius:8px;text-decoration:none;">
                View Dashboard &#8594;
              </a>
            </td>
          </tr>
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1.0" />
  <title>DealerHunters Daily Digest &mdash; {today}</title>
</head>
<body style="margin:0;padding:0;background:#F9FAFB;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#F9FAFB;padding:32px 16px 48px;">
<tr><td align="center">
<table border="0" cellpadding="0" cellspacing="0" width="600" style="max-width:600px;width:100%;">

  <!-- Header -->
  <tr>
    <td style="background:#111827;border-bottom:3px solid #10B981;padding:22px 28px;border-radius:12px 12px 0 0;">
      <div style="font-size:22px;font-weight:800;letter-spacing:-0.5px;color:#ffffff;line-height:1;">
        Dealer<span style="color:#10B981;">Hunters</span>
      </div>
      <div style="font-size:12px;color:rgba(255,255,255,0.42);margin-top:4px;">Dealer signals. Delivered daily.</div>
    </td>
  </tr>

  <!-- Summary -->
  <tr>
    <td style="background:#ffffff;padding:22px 28px 0;border-left:1px solid #E8ECF4;border-right:1px solid #E8ECF4;">
      <div style="font-size:12px;color:#9CA3AF;margin-bottom:4px;">{today}</div>
      <div style="font-size:22px;font-weight:700;color:#1A1F36;">
        {n} new {"opportunity" if n == 1 else "opportunities"} detected overnight
      </div>
    </td>
  </tr>

  <!-- Stats row -->
  <tr>
    <td style="background:#ffffff;padding:18px 28px 0;border-left:1px solid #E8ECF4;border-right:1px solid #E8ECF4;">
      <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td align="center" style="background:#F9FAFB;border:1px solid #E8ECF4;border-radius:8px;padding:12px 6px;">
            <div style="font-size:22px;font-weight:800;color:#111827;">{ownership}</div>
            <div style="font-size:10px;color:#9CA3AF;margin-top:3px;font-weight:500;">Ownership Changes</div>
          </td>
          <td width="8"></td>
          <td align="center" style="background:#F9FAFB;border:1px solid #E8ECF4;border-radius:8px;padding:12px 6px;">
            <div style="font-size:22px;font-weight:800;color:#111827;">{hiring}</div>
            <div style="font-size:10px;color:#9CA3AF;margin-top:3px;font-weight:500;">Marketing Hires</div>
          </td>
          <td width="8"></td>
          <td align="center" style="background:#F9FAFB;border:1px solid #E8ECF4;border-radius:8px;padding:12px 6px;">
            <div style="font-size:22px;font-weight:800;color:#111827;">{leadership}</div>
            <div style="font-size:10px;color:#9CA3AF;margin-top:3px;font-weight:500;">Leadership Changes</div>
          </td>
          <td width="8"></td>
          <td align="center" style="background:#F9FAFB;border:1px solid #E8ECF4;border-radius:8px;padding:12px 6px;">
            <div style="font-size:22px;font-weight:800;color:#10B981;">{avg_score}</div>
            <div style="font-size:10px;color:#9CA3AF;margin-top:3px;font-weight:500;">Avg Score</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Divider -->
  <tr>
    <td style="background:#ffffff;padding:18px 28px 0;border-left:1px solid #E8ECF4;border-right:1px solid #E8ECF4;">
      <hr style="border:none;border-top:1px solid #E8ECF4;margin:0;" />
    </td>
  </tr>

  <!-- Cards -->
  <tr>
    <td style="background:#ffffff;padding:18px 28px 24px;border-left:1px solid #E8ECF4;border-right:1px solid #E8ECF4;">
      {cards}
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="background:#F3F4F6;padding:18px 28px;border:1px solid #E8ECF4;border-top:none;
               border-radius:0 0 12px 12px;text-align:center;">
      <div style="font-size:12px;color:#9CA3AF;">
        Sent by <strong style="color:#6B7280;">DealerHunters</strong>
        &nbsp;&middot;&nbsp;
        <a href="{DASHBOARD_URL}" style="color:#9CA3AF;">View Dashboard</a>
        &nbsp;&middot;&nbsp;
        <a href="mailto:unsubscribe@dealerhunters.io?subject=Unsubscribe" style="color:#9CA3AF;">Unsubscribe</a>
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def build_empty_html():
    today = datetime.utcnow().strftime("%B %d, %Y")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>DealerHunters &mdash; No New Signals</title>
</head>
<body style="margin:0;padding:0;background:#F9FAFB;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#F9FAFB;padding:32px 16px 48px;">
<tr><td align="center">
<table border="0" cellpadding="0" cellspacing="0" width="600" style="max-width:600px;width:100%;">
  <tr>
    <td style="background:#111827;border-bottom:3px solid #10B981;padding:22px 28px;border-radius:12px 12px 0 0;">
      <div style="font-size:22px;font-weight:800;letter-spacing:-0.5px;color:#ffffff;line-height:1;">
        Dealer<span style="color:#10B981;">Hunters</span>
      </div>
      <div style="font-size:12px;color:rgba(255,255,255,0.42);margin-top:4px;">Dealer signals. Delivered daily.</div>
    </td>
  </tr>
  <tr>
    <td style="background:#ffffff;padding:48px 28px;border:1px solid #E8ECF4;border-top:none;text-align:center;">
      <div style="font-size:36px;margin-bottom:14px;">&#128269;</div>
      <div style="font-size:18px;font-weight:600;color:#1A1F36;margin-bottom:8px;">No new signals detected today</div>
      <div style="font-size:14px;color:#6B7280;margin-bottom:24px;line-height:1.6;">
        The pipeline ran successfully on {today}.<br>No new dealership signals matched our criteria overnight.
      </div>
      <a href="{DASHBOARD_URL}"
        style="display:inline-block;background:#10B981;color:#ffffff;font-size:13px;
               font-weight:600;padding:10px 22px;border-radius:8px;text-decoration:none;">
        View Dashboard
      </a>
    </td>
  </tr>
  <tr>
    <td style="background:#F3F4F6;padding:18px 28px;border:1px solid #E8ECF4;border-top:none;
               border-radius:0 0 12px 12px;text-align:center;">
      <div style="font-size:12px;color:#9CA3AF;">
        Sent by <strong style="color:#6B7280;">DealerHunters</strong>
        &nbsp;&middot;&nbsp;
        <a href="{DASHBOARD_URL}" style="color:#9CA3AF;">View Dashboard</a>
        &nbsp;&middot;&nbsp;
        <a href="mailto:unsubscribe@dealerhunters.io?subject=Unsubscribe" style="color:#9CA3AF;">Unsubscribe</a>
      </div>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


# ── Send ───────────────────────────────────────────────────────────────────
if count > 0:
    subject   = f"DealerHunters: {count} new {'opportunity' if count == 1 else 'opportunities'} — {datetime.utcnow().strftime('%b %d')}"
    html_body = build_html(opps)
else:
    subject   = f"DealerHunters: No new signals today — {datetime.utcnow().strftime('%b %d')}"
    html_body = build_empty_html()

try:
    email = resend.Emails.send({
        "from":    DIGEST_EMAIL_FROM,
        "to":      [DIGEST_EMAIL_TO],
        "subject": subject,
        "html":    html_body,
    })
    email_id = email.get("id") if isinstance(email, dict) else getattr(email, "id", None)
    print(f"Digest sent to {DIGEST_EMAIL_TO} (id: {email_id})")
except Exception as e:
    print(f"Failed to send digest: {e}")
    raise

# ── Log to Supabase ────────────────────────────────────────────────────────
try:
    supabase.table("digest_log").insert({
        "sent_at":             datetime.utcnow().isoformat(),
        "opportunities_count": count,
        "recipient":           DIGEST_EMAIL_TO,
        "status":              "sent",
        "resend_id":           email_id,
    }).execute()
    print("Logged to digest_log")
except Exception as e:
    print(f"digest_log insert failed (non-fatal): {e}")

print("Daily digest complete.")
