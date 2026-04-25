from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.articles.models import Article
from apps.contacts.forms import ContactCreateForm, ContactEditForm
from apps.contacts.models import Contact
from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin
from apps.core.views import JournalOwnedCreateView, JournalOwnedPatchView
from apps.reviews.models import ReviewRequest


class ContactCreateView(JournalOwnedCreateView):
    form_class = ContactCreateForm
    template_name = "contacts/create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "GET":
            role = self.request.GET.get("role", "")
            if role in Contact.Role.values:
                kwargs["initial"] = {"usual_roles": [role]}
        return kwargs

    def post_create(self, instance, form):
        messages.success(self.request, f"Contact {instance.full_name} ajouté.")

    def get_success_url(self, instance):
        return reverse("contacts:list", kwargs={"slug": self.request.journal.slug})


class ContactListView(JournalMemberRequiredMixin, View):
    def get(self, request, **kwargs):
        contacts = (
            Contact.objects
            .filter(journal=request.journal)
            .annotate(
                article_count=Count("authored_articles", distinct=True),
                review_count=Count("reviewrequest", distinct=True),
            )
        )
        return render(request, "contacts/list.html", {
            "journal": request.journal,
            "user_journal_count": request.user.memberships.count(),
            "contacts": contacts,
            "roles": Contact.Role,
        })


class ContactDetailView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):
    model = Contact

    def get(self, request, **kwargs):
        contact = self.get_object_or_404()
        articles = (
            Article.objects
            .filter(author=contact)
            .select_related("issue")
            .order_by("-created_at")
        )
        reviews = (
            ReviewRequest.objects
            .filter(reviewer=contact)
            .select_related("article", "article__issue", "article_version")
            .order_by("-created_at")
        )
        form = ContactEditForm(instance=contact)
        return render(request, "contacts/detail.html", {
            "journal": request.journal,
            "user_journal_count": request.user.memberships.count(),
            "contact": contact,
            "articles": articles,
            "reviews": reviews,
            "form": form,
            "patch_url": reverse(
                "contacts:patch",
                kwargs={"slug": request.journal.slug, "pk": contact.pk},
            ),
            "edit_url": reverse(
                "contacts:edit",
                kwargs={"slug": request.journal.slug, "pk": contact.pk},
            ),
            "delete_url": reverse(
                "contacts:delete",
                kwargs={"slug": request.journal.slug, "pk": contact.pk},
            ),
        })


class ContactPatchView(JournalOwnedPatchView):
    model = Contact
    ALLOWED_FIELDS = {"first_name", "last_name", "email", "affiliation", "notes"}


class ContactEditView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):
    model = Contact

    def post(self, request, **kwargs):
        contact = self.get_object_or_404()
        form = ContactEditForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            url = reverse(
                "contacts:detail",
                kwargs={"slug": request.journal.slug, "pk": contact.pk},
            )
            return JsonResponse({"redirect_url": url})
        errors = {
            field: [str(e.message) for e in errs]
            for field, errs in form.errors.as_data().items()
        }
        return JsonResponse({"errors": errors}, status=400)


class ContactSearchAPIView(JournalMemberRequiredMixin, View):
    def get(self, request, **kwargs):
        q = request.GET.get("q", "").strip()
        role = request.GET.get("role", "")

        contacts = Contact.objects.filter(journal=request.journal)
        if q:
            contacts = contacts.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(affiliation__icontains=q)
            )
        if role and role in Contact.Role.values:
            contacts = contacts.filter(usual_roles__contains=[role])

        results = [
            {"id": c.pk, "name": c.full_name, "affiliation": c.affiliation}
            for c in contacts.order_by("last_name", "first_name")[:10]
        ]
        return JsonResponse({"results": results})


class ContactDeleteView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):
    model = Contact

    def delete(self, request, **kwargs):
        contact = self.get_object_or_404()
        with transaction.atomic():
            Article.objects.filter(
                author=contact, author_name_override=""
            ).update(author_name_override=contact.full_name)
            Article.objects.filter(author=contact).update(author=None)
            contact.hard_delete()
        url = reverse("contacts:list", kwargs={"slug": request.journal.slug})
        return JsonResponse({"redirect_url": url})
