import os
import resend
import html
import markdown


def send_email(
    subject: str,
    body_text: str,
    body_html: str = None,
    recipients: list = None,
    api_key: str = None,
):
    # Accept api_key as param, fall back to env only if not passed
    if not api_key:
        api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise ValueError("No Resend API key provided")

    if not recipients:
        to_email = os.environ.get("MY_EMAIL")
        if not to_email:
            raise ValueError("No recipients provided")
        recipients = [to_email]

    recipients = [r for r in recipients if r is not None]
    if not recipients:
        raise ValueError("No valid recipients provided")

    resend.api_key = api_key

    params = {
        "from": "Digest <onboarding@resend.dev>",
        "to": recipients,
        "subject": subject,
        "text": body_text,
    }
    if body_html:
        params["html"] = body_html

    return resend.Emails.send(params)


def markdown_to_html(markdown_text: str) -> str:
    html_body = markdown.markdown(markdown_text, extensions=['extra', 'nl2br'])
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        h2 {{ font-size: 18px; font-weight: 600; color: #1a1a1a; margin-top: 24px; margin-bottom: 8px; }}
        h3 {{ font-size: 16px; font-weight: 600; color: #1a1a1a; margin-top: 20px; margin-bottom: 8px; }}
        p {{ margin: 8px 0; color: #4a4a4a; }}
        strong {{ font-weight: 600; color: #1a1a1a; }}
        a {{ color: #0066cc; text-decoration: none; font-weight: 500; }}
        hr {{ border: none; border-top: 1px solid #e5e5e5; margin: 20px 0; }}
        .article-link {{ display: inline-block; margin-top: 8px; color: #0066cc; font-size: 14px; }}
    </style>
</head>
<body>{html_body}</body>
</html>"""


def digest_to_html(digest_response) -> str:
    from app.agent.email_agent import EmailDigestResponse

    if not isinstance(digest_response, EmailDigestResponse):
        return markdown_to_html(str(digest_response))

    html_parts = []
    greeting_html     = markdown.markdown(digest_response.introduction.greeting, extensions=['extra', 'nl2br'])
    introduction_html = markdown.markdown(digest_response.introduction.introduction, extensions=['extra', 'nl2br'])
    html_parts.append(f'<div class="greeting">{greeting_html}</div>')
    html_parts.append(f'<div class="introduction">{introduction_html}</div>')
    html_parts.append('<hr>')

    for article in digest_response.articles:
        html_parts.append(f'<h3>{html.escape(article.title)}</h3>')
        summary_html = markdown.markdown(article.summary, extensions=['extra', 'nl2br'])
        html_parts.append(f'<div>{summary_html}</div>')
        html_parts.append(f'<p><a href="{html.escape(article.url)}" class="article-link">Read more →</a></p>')
        html_parts.append('<hr>')

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        h3 {{ font-size: 16px; font-weight: 600; color: #1a1a1a; margin-top: 20px; margin-bottom: 8px; }}
        p {{ margin: 8px 0; color: #4a4a4a; }}
        a {{ color: #0066cc; text-decoration: none; }}
        hr {{ border: none; border-top: 1px solid #e5e5e5; margin: 20px 0; }}
        .greeting {{ font-size: 16px; font-weight: 500; color: #1a1a1a; margin-bottom: 12px; }}
        .introduction {{ color: #4a4a4a; margin-bottom: 20px; }}
        .article-link {{ display: inline-block; margin-top: 8px; font-size: 14px; }}
        div {{ margin: 8px 0; color: #4a4a4a; }}
    </style>
</head>
<body>{''.join(html_parts)}</body>
</html>"""


def send_email_to_self(subject: str, body: str):
    send_email(subject, body)