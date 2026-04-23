from django.template.loader import render_to_string

from apps.articles.models import InternalNote
from apps.reviews.models import ReviewRequest


def log_action(article, actor, message):
    InternalNote.objects.create(
        article=article,
        author=actor,
        content=message,
        is_automatic=True,
    )


def article_counter_ctx(article):
    version_count = article.versions.count()
    rr = list(article.review_requests.all())
    reviews_received = sum(1 for r in rr if r.state == ReviewRequest.State.RECEIVED)
    return {
        "version_count": version_count,
        "review_request_count": len(rr),
        "reviews_received": reviews_received,
    }


def oob_counters_html(article, request=None):
    ctx = article_counter_ctx(article)
    ctx["oob"] = True
    return render_to_string("articles/_header_counters.html", ctx, request=request)
