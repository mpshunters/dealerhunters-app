"""
Send an immediate email alert for each hot lead created in the last 2 hours.
Runs after create_opportunities.py in the daily pipeline.
Skips silently if no hot leads exist.
"""

from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone, timedelta
import resend
import os
import urllib.parse

load_dotenv()

SUPABASE_URL      = os.environ.get("SUPABASE_URL")
SUPABASE_KEY      = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
RESEND_API_KEY    = os.environ.get("RESEND_API_KEY")
DIGEST_EMAIL_TO   = os.environ.get("DIGEST_EMAIL_TO")
DIGEST_EMAIL_FROM = os.environ.get("DIGEST_EMAIL_FROM", "DealerHunters Signals <signals@mpshunters.com>")
DASHBOARD_URL     = "https://dealerhunters-app.pages.dev/dashboard"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not RESEND_API_KEY:
    raise Exception("Missing RESEND_API_KEY")
if not DIGEST_EMAIL_TO:
    raise Exception("Missing DIGEST_EMAIL_TO")

resend.api_key = RESEND_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("DealerHunters hot lead alert starting...")

# ── Fetch hot leads created in last 2 hours ────────────────────────────────
since = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

hot_leads = (
    supabase.table("opportunities")
    .select("*")
    .eq("is_hot_lead", True)
    .gte("created_at", since)
    .order("confidence_score", desc=True)
    .execute()
    .data or []
)

if not hot_leads:
    print("No hot leads in the last 2 hours — skipping alert.")
    raise SystemExit(0)

print(f"Found {len(hot_leads)} hot lead(s) — sending alerts...")

# ── Signal metadata ────────────────────────────────────────────────────────
SIGNAL_STYLES = {
    "ownership_change":  ("Ownership Change",  "#065F46", "#ECFDF5"),
    "hiring":            ("Marketing Hire",    "#1E40AF", "#EFF6FF"),
    "new_rooftop":       ("New Rooftop",       "#166534", "#F0FDF4"),
    "oem_event":         ("OEM Event",         "#6B21A8", "#FAF5FF"),
    "weak_digital":      ("Weak Digital",      "#92400E", "#FFFBEB"),
    "Ownership Change":  ("Ownership Change",  "#065F46", "#ECFDF5"),
    "Marketing Hire":    ("Marketing Hire",    "#1E40AF", "#EFF6FF"),
    "Leadership Change": ("Leadership Change", "#6B21A8", "#FAF5FF"),
    "Expansion":         ("Expansion",         "#166534", "#F0FDF4"),
}
DEFAULT_SIGNAL = ("Signal", "#344054", "#F2F4F7")


def signal_info(opp):
    raw = opp.get("signal_type") or opp.get("opportunity_type") or ""
    return SIGNAL_STYLES.get(raw, DEFAULT_SIGNAL)


def signal_count_from_score(score):
    """Reverse-map confidence score → number of signals detected."""
    if score >= 92:
        return 3
    if score >= 83:
        return 2
    return 1


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def apollo_url(dealer_name):
    q = urllib.parse.quote(dealer_name or "")
    return f"https://app.apollo.io/#/people?q_organization_name={q}"


# ── Email builder ──────────────────────────────────────────────────────────
def build_hot_lead_html(opp):
    label, sig_color, sig_bg = signal_info(opp)
    name     = esc(opp.get("dealership_name") or "Unnamed Dealership")
    city     = esc(opp.get("city") or "")
    state    = esc(opp.get("state") or "")
    location = f"{city}, {state}" if city and state else city or state or "Location unavailable"
    summary  = esc(opp.get("ai_summary") or "No summary available.")
    pitch    = esc(opp.get("pitch_angle") or opp.get("recommended_offer") or "")
    score    = int(opp.get("confidence_score") or opp.get("fit_score") or 0)
    phone    = opp.get("phone")
    website  = opp.get("website")
    n_sigs   = signal_count_from_score(score)
    raw_name = opp.get("dealership_name") or ""
    today    = datetime.utcnow().strftime("%B %d, %Y · %H:%M UTC")

    pitch_block = ""
    if pitch:
        pitch_block = f"""
        <tr>
          <td style="padding:0 28px 20px;">
            <div style="background:#1A2433;border-radius:10px;padding:16px 18px;">
              <div style="font-size:10px;font-weight:700;color:#10B981;letter-spacing:0.8px;
                          text-transform:uppercase;margin-bottom:8px;">Suggested Pitch</div>
              <div style="font-size:14px;color:#E5E7EB;line-height:1.65;">{pitch}</div>
            </div>
          </td>
        </tr>"""

    phone_row = ""
    if phone:
        phone_row = f"""
        <tr>
          <td style="padding:0 28px 12px;">
            <span style="font-size:13px;color:#6B7280;">&#128222;&nbsp;{esc(phone)}</span>
          </td>
        </tr>"""

    website_row = ""
    if website:
        website_row = f"""
        <tr>
          <td style="padding:0 28px 20px;">
            <a href="{esc(website)}" style="font-size:13px;color:#10B981;text-decoration:none;">
              &#127758;&nbsp;{esc(website)}
            </a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1.0" />
  <title>&#128293; Hot Lead: {name}</title>
</head>
<body style="margin:0;padding:0;background:#0F1117;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
<table border="0" cellpadding="0" cellspacing="0" width="100%"
       style="background:#0F1117;padding:32px 16px 48px;">
<tr><td align="center">
<table border="0" cellpadding="0" cellspacing="0" width="600" style="max-width:600px;width:100%;">

  <!-- Header -->
  <tr>
    <td style="background:#111827;border-bottom:3px solid #10B981;
               padding:22px 28px;border-radius:12px 12px 0 0;">
      <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td>
            <div style="font-size:22px;font-weight:800;letter-spacing:-0.5px;color:#ffffff;line-height:1;">
              Dealer<span style="color:#10B981;">Hunters</span>
            </div>
            <div style="font-size:11px;color:rgba(255,255,255,0.4);margin-top:4px;">
              Dealer signals. Delivered daily.
            </div>
          </td>
          <td align="right" valign="middle">
            <span style="display:inline-block;background:#FF4500;color:#ffffff;font-size:11px;
                         font-weight:700;padding:4px 12px;border-radius:999px;
                         letter-spacing:0.4px;">&#128293; HOT LEAD</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Headline -->
  <tr>
    <td style="background:#111827;padding:28px 28px 0;">
      <div style="font-size:30px;font-weight:800;color:#10B981;line-height:1.1;
                  letter-spacing:-0.5px;">&#128293; Hot Lead Detected</div>
      <div style="font-size:12px;color:rgba(255,255,255,0.35);margin-top:8px;">{today}</div>
    </td>
  </tr>

  <!-- Dealership block -->
  <tr>
    <td style="background:#111827;padding:20px 28px 0;">
      <table border="0" cellpadding="0" cellspacing="0" width="100%"
             style="background:#1A2433;border:1px solid #2D3748;border-left:4px solid #10B981;
                    border-radius:10px;padding:0;">
        <tr>
          <td style="padding:20px 20px 8px;">
            <div style="font-size:22px;font-weight:800;color:#F9FAFB;line-height:1.2;">{name}</div>
            <div style="font-size:14px;color:#9CA3AF;margin-top:6px;">&#128205;&nbsp;{location}</div>
          </td>
          <td width="60" align="right" valign="top" style="padding:20px 20px 8px;">
            <div style="width:52px;height:52px;border-radius:50%;background:#0D1F14;
                        border:2px solid #10B981;text-align:center;line-height:52px;
                        font-size:20px;font-weight:900;color:#10B981;">{score}</div>
          </td>
        </tr>
        <tr>
          <td colspan="2" style="padding:4px 20px 20px;">
            <span style="display:inline-block;font-size:11px;font-weight:700;padding:4px 12px;
                         border-radius:999px;color:{sig_color};background:{sig_bg};
                         letter-spacing:0.3px;">{label}</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Why it's hot -->
  <tr>
    <td style="background:#111827;padding:20px 28px 0;">
      <div style="background:#1C2B1C;border:1px solid #10B981;border-radius:10px;
                  padding:14px 18px;display:block;">
        <div style="font-size:13px;font-weight:700;color:#10B981;margin-bottom:4px;">
          Why it&rsquo;s hot
        </div>
        <div style="font-size:14px;color:#D1FAE5;line-height:1.6;">
          &#128293;&nbsp;<strong>{n_sigs} signal{"s" if n_sigs != 1 else ""} detected</strong>
          for this dealership &mdash; multiple buying triggers indicate a high-probability window.
        </div>
      </div>
    </td>
  </tr>

  <!-- White card: rest of details -->
  <tr>
    <td style="background:#111827;padding:16px 0 0;">
      <table border="0" cellpadding="0" cellspacing="0" width="100%"
             style="background:#1E293B;border-radius:10px;margin:0 28px;width:calc(100% - 56px);">

        <!-- AI Summary -->
        <tr>
          <td style="padding:20px 18px 16px;">
            <div style="font-size:10px;font-weight:700;color:#64748B;letter-spacing:0.8px;
                        text-transform:uppercase;margin-bottom:8px;">Signal Summary</div>
            <div style="font-size:14px;color:#CBD5E1;line-height:1.7;">{summary}</div>
          </td>
        </tr>

      </table>
    </td>
  </tr>

  <!-- Pitch block -->
  <tr>
    <td style="background:#111827;padding:14px 28px 0;">
      {f'''<div style="background:#1A2433;border-radius:10px;padding:16px 18px;">
        <div style="font-size:10px;font-weight:700;color:#10B981;letter-spacing:0.8px;
                    text-transform:uppercase;margin-bottom:8px;">Suggested Pitch</div>
        <div style="font-size:14px;color:#E5E7EB;line-height:1.65;">{pitch}</div>
      </div>''' if pitch else ''}
    </td>
  </tr>

  <!-- Contact info -->
  {f'''<tr>
    <td style="background:#111827;padding:14px 28px 0;">
      <div style="font-size:13px;color:#94A3B8;">&#128222;&nbsp;{esc(phone)}</div>
    </td>
  </tr>''' if phone else ''}
  {f'''<tr>
    <td style="background:#111827;padding:8px 28px 0;">
      <a href="{esc(website)}" style="font-size:13px;color:#10B981;text-decoration:none;">
        &#127758;&nbsp;{esc(website)}
      </a>
    </td>
  </tr>''' if website else ''}

  <!-- CTA buttons -->
  <tr>
    <td style="background:#111827;padding:24px 28px 28px;">
      <table border="0" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <a href="{DASHBOARD_URL}"
               style="display:inline-block;background:#10B981;color:#ffffff;font-size:13px;
                      font-weight:700;padding:11px 22px;border-radius:8px;
                      text-decoration:none;letter-spacing:0.2px;">
              View Dashboard &#8594;
            </a>
          </td>
          <td width="12"></td>
          <td>
            <a href="{apollo_url(raw_name)}"
               style="display:inline-block;background:#1A2433;color:#10B981;font-size:13px;
                      font-weight:700;padding:11px 22px;border-radius:8px;
                      text-decoration:none;border:1px solid #10B981;letter-spacing:0.2px;">
              Find Contact &#8594;
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="background:#0D1117;padding:16px 28px;border-radius:0 0 12px 12px;
               border-top:1px solid #1E293B;text-align:center;">
      <div style="font-size:11px;color:#4B5563;">
        Sent by <strong style="color:#6B7280;">DealerHunters</strong>
        &nbsp;&middot;&nbsp;
        <a href="mailto:signals@mpshunters.com" style="color:#4B5563;text-decoration:none;">
          signals@mpshunters.com
        </a>
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── Send one email per hot lead ────────────────────────────────────────────
sent = 0
for opp in hot_leads:
    dealer_name = opp.get("dealership_name") or "Unknown Dealership"
    city        = opp.get("city") or ""
    state       = opp.get("state") or ""
    location    = f"{city}, {state}" if city and state else city or state or "Unknown Location"

    subject  = f"🔥 Hot Lead: {dealer_name} | {location}"
    html     = build_hot_lead_html(opp)
    email_id = None

    try:
        result   = resend.Emails.send({
            "from":    DIGEST_EMAIL_FROM,
            "to":      [DIGEST_EMAIL_TO],
            "subject": subject,
            "html":    html,
        })
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        print(f"  Alert sent for {dealer_name} (id: {email_id})")
        sent += 1
    except Exception as e:
        print(f"  Failed to send alert for {dealer_name}: {e}")

    try:
        supabase.table("digest_log").insert({
            "sent_at":             datetime.utcnow().isoformat(),
            "opportunities_count": 1,
            "recipient":           DIGEST_EMAIL_TO,
            "status":              "sent" if email_id else "error",
            "resend_id":           email_id,
            "type":                "hot_lead_alert",
        }).execute()
    except Exception as e:
        print(f"  digest_log insert failed (non-fatal): {e}")

print(f"\nHot lead alerts complete — {sent}/{len(hot_leads)} sent.")
