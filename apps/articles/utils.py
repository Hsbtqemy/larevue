from django.db.models import Count, Q
from django.template.loader import render_to_string

from apps.reviews.models import ReviewRequest


def article_counter_ctx(article):
    agg = article.review_requests.aggregate(
        review_request_count=Count("id"),
        reviews_received=Count("id", filter=Q(state=ReviewRequest.State.RECEIVED)),
    )
    return {
        "version_count": article.versions.count(),
        "review_request_count": agg["review_request_count"],
        "reviews_received": agg["reviews_received"],
    }


def oob_counters_html(article, request=None):
    return render_to_string(
        "articles/_header_counters.html",
        {**article_counter_ctx(article), "oob": True},
        request=request,
    )
