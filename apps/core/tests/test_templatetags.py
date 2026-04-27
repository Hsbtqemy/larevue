import datetime

import pytest
from django.template import Context, Template

from apps.core.templatetags.edito import (
    date_calendar,
    date_compact,
    date_short,
    days_late,
    icon,
    to_json,
)


# ------------------------------------------------------------------ #
# Filters                                                              #
# ------------------------------------------------------------------ #

class TestDateShort:
    @pytest.mark.parametrize("date,expected", [
        (datetime.date(2026, 1, 14), "14 janv. 2026"),
        (datetime.date(2026, 3, 1),  "1 mars 2026"),
        (datetime.date(2026, 5, 31), "31 mai 2026"),
        (datetime.date(2026, 12, 25), "25 déc. 2026"),
    ])
    def test_format(self, date, expected):
        assert date_short(date) == expected

    def test_none_returns_empty(self):
        assert date_short(None) == ""


class TestDateCompact:
    def test_format(self):
        assert date_compact(datetime.date(2026, 1, 14)) == "14/01/26"

    def test_none_returns_empty(self):
        assert date_compact(None) == ""


class TestDateCalendar:
    def test_returns_dict(self):
        result = date_calendar(datetime.date(2026, 1, 14))
        assert result == {"day": 14, "month": "janv"}

    def test_no_trailing_period(self):
        for month in range(1, 13):
            d = datetime.date(2026, month, 1)
            assert not date_calendar(d)["month"].endswith(".")

    def test_none_returns_empty_dict(self):
        assert date_calendar(None) == {}


class TestDaysLate:
    def test_past_date_positive(self):
        past = datetime.date.today() - datetime.timedelta(days=5)
        assert days_late(past) == 5

    def test_future_date_negative(self):
        future = datetime.date.today() + datetime.timedelta(days=3)
        assert days_late(future) == -3

    def test_today_is_zero(self):
        assert days_late(datetime.date.today()) == 0

    def test_none_returns_zero(self):
        assert days_late(None) == 0


# ------------------------------------------------------------------ #
# {% icon %}                                                           #
# ------------------------------------------------------------------ #

class TestIconTag:
    def test_returns_svg_element(self):
        result = icon("home")
        assert result.startswith("<svg")
        assert "</svg>" in result

    def test_default_size_16(self):
        result = icon("home")
        assert 'width="16"' in result
        assert 'height="16"' in result

    def test_custom_size(self):
        result = icon("home", size=24)
        assert 'width="24"' in result

    def test_unknown_name_returns_empty(self):
        result = icon("nonexistent-icon")
        assert result == ""

    def test_css_class(self):
        result = icon("home", cls="my-icon")
        assert 'class="my-icon"' in result

    def test_svg_attrs(self):
        result = icon("check")
        assert 'fill="none"' in result
        assert 'stroke="currentColor"' in result
        assert 'stroke-width="1.6"' in result

    def test_template_tag_syntax(self):
        tpl = Template('{% load edito %}{% icon "check" size=20 %}')
        rendered = tpl.render(Context({}))
        assert '<svg' in rendered
        assert 'width="20"' in rendered


# ------------------------------------------------------------------ #
# {% state_badge %} and {% verdict_badge %}                            #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
class TestStateBadge:
    def test_renders_badge_for_issue(self, issue):
        tpl = Template("{% load edito %}{% state_badge issue %}")
        rendered = tpl.render(Context({"issue": issue}))
        assert "badge" in rendered
        assert issue.get_state_display() in rendered
        assert issue.get_badge_tone() in rendered

    def test_renders_badge_for_article(self, article):
        tpl = Template("{% load edito %}{% state_badge article %}")
        rendered = tpl.render(Context({"article": article}))
        assert "badge" in rendered
        assert article.get_state_display() in rendered


class TestVerdictBadge:
    @pytest.mark.parametrize("verdict,expected_tone,expected_label", [
        ("favorable", "done", "Favorable"),
        ("needs_revision", "progress-tone", "Révision requise"),
        ("unfavorable", "refused", "Défavorable"),
    ])
    def test_renders_verdict(self, verdict, expected_tone, expected_label):
        tpl = Template("{% load edito %}{% verdict_badge verdict %}")
        rendered = tpl.render(Context({"verdict": verdict}))
        assert expected_tone in rendered
        assert expected_label in rendered

    def test_unknown_verdict_fallback(self):
        tpl = Template("{% load edito %}{% verdict_badge verdict %}")
        rendered = tpl.render(Context({"verdict": "unknown"}))
        assert "neutral" in rendered
        assert "unknown" in rendered


class TestToJson:
    def test_list_of_tuples_html_escaped(self):
        result = to_json([["article", "Article"], ["note", "Note"]])
        assert "&quot;" in result
        assert '"' not in str(result)

    def test_safe_string_for_html_attribute(self):
        result = to_json([["a", "b"]])
        rendered = f'x-data="fn({result})"'
        # The attribute string must not contain unescaped double-quotes inside
        inner = rendered[len('x-data="fn('):-len(')"')]
        assert '"' not in inner

    def test_non_ascii_preserved(self):
        result = to_json([["val", "Éditorial"]])
        assert "Éditorial" in str(result)

    def test_empty_list(self):
        result = to_json([])
        assert str(result) == "[]"
