import uuid
from urllib.parse import urlparse
from typing import List, Dict, Optional, Any


def _is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except (ValueError, TypeError):
        return False


def _is_untrusted_domain(url: str, untrusted_domains: List[str] | None = None) -> bool:
    if not untrusted_domains:
        return False

    try:
        hostname = urlparse(url).hostname

        if not hostname:
            return True

        hostname = hostname.lower().rstrip(".")

        return any(
            hostname == domain.lower().lstrip(".").rstrip(".")
            or hostname.endswith("." + domain.lower().lstrip(".").rstrip("."))
            for domain in untrusted_domains
            )

    except (ValueError, TypeError):

        return True


def build_search_context(search_results: List[Dict[str, Any]], untrusted_domains: Optional[List[str]] = None) -> str:
    grouped_sources = {}

    for result in search_results:
        url = result.get('url', '')
        title = result.get('title', 'No title provided')
        content = result.get('content', '')

        if not content:
            continue

        # Sanitize URL
        if not _is_valid_url(url) or _is_untrusted_domain(url):
            url = "[INVALID_OR_TRACKING_URL_DO_NOT_CITE]"
            # If the URL is invalid, we MUST use a unique key so they don't group together
            dict_key = f"invalid_{uuid.uuid4()}"
        else:
            # If valid, use the actual URL as the key so identical URLs merge
            dict_key = url

        # Grouping logic
        if dict_key in grouped_sources:
            if content not in grouped_sources[dict_key]['content_list']:
                grouped_sources[dict_key]['content_list'].append(content)
        else:
            grouped_sources[dict_key] = {
                'title': title,
                'content_list': [content],
                'url': url  # Store the real URL or the placeholder string
                }

    formatted_context = []

    # Assign numbers [1], [2], etc. to the deduplicated dictionary
    for i, (key, data) in enumerate(grouped_sources.items(), 1):
        merged_content = "\n\n[Additional context from same source]\n".join(data['content_list'])

        # Use data['url'] here so the placeholder text is printed for invalid URLs
        formatted_block = f"[{i}] Source Title: {data['title']}\nSource URL: {data['url']}\nContent: {merged_content}"
        formatted_context.append(formatted_block)

    return "\n\n---\n\n".join(formatted_context)
