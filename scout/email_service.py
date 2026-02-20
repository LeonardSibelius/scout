"""
Email Digest Service — Sends daily opportunity summaries via Resend.
"""

import os
from typing import List, Dict
from datetime import datetime
from .database import log_email

# Optional: Resend for email delivery
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False


def send_daily_digest(opportunities: List[Dict]) -> bool:
    """Send the daily email digest with top opportunities."""
    api_key = os.environ.get('RESEND_API_KEY')
    recipient = os.environ.get('SCOUT_EMAIL_TO', 'wpneural@gmail.com')
    from_email = os.environ.get('SCOUT_EMAIL_FROM', 'scout@resend.dev')

    if not api_key:
        print("[Email] RESEND_API_KEY not set — skipping email")
        return False

    if not RESEND_AVAILABLE:
        print("[Email] resend package not installed — skipping email")
        return False

    if not opportunities:
        print("[Email] No opportunities to send")
        return False

    resend.api_key = api_key

    subject = f"Scout Daily Brief — {datetime.now().strftime('%b %d')} — {len(opportunities)} opportunities"
    html = _build_digest_html(opportunities)

    try:
        resend.Emails.send({
            "from": from_email,
            "to": [recipient],
            "subject": subject,
            "html": html
        })
        log_email(len(opportunities), subject)
        print(f"[Email] Digest sent to {recipient} with {len(opportunities)} opportunities")
        return True
    except Exception as e:
        print(f"[Email] Failed to send: {e}")
        return False


def _build_digest_html(opportunities: List[Dict]) -> str:
    """Build the HTML email body."""
    date_str = datetime.now().strftime('%A, %B %d, %Y')

    domain_colors = {
        'ai_tech': '#6366f1',
        'local_business': '#10b981',
        'digital_product': '#f59e0b',
    }

    domain_labels = {
        'ai_tech': 'AI / Tech',
        'local_business': 'Local Business',
        'digital_product': 'Digital Product',
    }

    opp_cards = ""
    for opp in opportunities:
        domain = opp.get('domain', 'unknown')
        color = domain_colors.get(domain, '#6b7280')
        label = domain_labels.get(domain, domain)
        score = opp.get('score', 0)
        tags = opp.get('tags', '')

        score_bar = '█' * int(score) + '░' * (10 - int(score))

        opp_cards += f"""
        <div style="border:1px solid #e5e7eb; border-radius:8px; padding:16px; margin-bottom:12px; background:#fff;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="background:{color}; color:white; padding:2px 8px; border-radius:4px; font-size:12px;">{label}</span>
                <span style="font-family:monospace; font-size:12px; color:#6b7280;">{score_bar} {score}/10</span>
            </div>
            <h3 style="margin:0 0 6px 0; font-size:16px; color:#111827;">{opp.get('title', 'Untitled')}</h3>
            <p style="margin:0 0 8px 0; font-size:14px; color:#4b5563; line-height:1.4;">{opp.get('description', '')}</p>
            <div style="font-size:12px; color:#9ca3af;">
                {f'<a href="{opp["url"]}" style="color:{color};">View source →</a>' if opp.get('url') else ''}
                {f' · Tags: {tags}' if tags else ''}
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#f3f4f6; padding:20px; margin:0;">
        <div style="max-width:600px; margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1e1b4b,#312e81); color:white; padding:24px; border-radius:12px 12px 0 0;">
                <h1 style="margin:0; font-size:24px;">Scout Daily Brief</h1>
                <p style="margin:4px 0 0; opacity:0.8; font-size:14px;">{date_str}</p>
            </div>

            <div style="background:#f9fafb; padding:20px; border-radius:0 0 12px 12px;">
                <p style="color:#4b5563; margin:0 0 16px;">Found <strong>{len(opportunities)}</strong> opportunities worth your attention today:</p>
                {opp_cards}
                <div style="text-align:center; margin-top:20px;">
                    <p style="font-size:12px; color:#9ca3af;">
                        Scout Intelligence Agent — Engine Room AI<br>
                        <a href="#" style="color:#6366f1;">View Dashboard</a>
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html
