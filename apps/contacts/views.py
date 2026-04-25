from django.contrib import messages
from django.urls import reverse

from apps.contacts.forms import ContactCreateForm
from apps.core.views import JournalOwnedCreateView


class ContactCreateView(JournalOwnedCreateView):
    form_class = ContactCreateForm
    template_name = "contacts/create.html"

    def post_create(self, instance, form):
        messages.success(self.request, f"Contact {instance.full_name} ajouté.")

    def get_success_url(self, instance):
        return reverse("journal_dashboard", kwargs={"slug": self.request.journal.slug})
