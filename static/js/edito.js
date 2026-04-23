/**
 * Alpine.js components for Edito.
 *
 * Global event contract: mutating components dispatch a 'saved' custom event
 * (bubbles to window). savedBanner(), mounted on <body>, listens with
 * @saved.window and shows a confirmation message.
 * Event detail: { label: string }
 */

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? match[1] : "";
}

document.addEventListener("alpine:init", () => {

  Alpine.data("inlineEdit", (value, patchUrl, fieldName, inputType = "text", options = []) => ({
    editing: false,
    draft: value,
    type: inputType,
    saving: false,
    justSaved: false,
    error: null,

    get displayDraft() {
      if (options.length) {
        const match = options.find(o => String(o[0]) === String(this.draft));
        return match ? match[1] : this.draft;
      }
      return this.draft;
    },

    startEdit() {
      this.editing = true;
      this.$nextTick(() => {
        const ref =
          this.type === "textarea" ? this.$refs.inputTextarea :
          this.type === "select"   ? this.$refs.inputSelect   :
                                     this.$refs.inputText;
        if (ref) { ref.focus(); if (ref.select) ref.select(); }
      });
    },

    cancel() {
      this.draft = value;
      this.editing = false;
      this.error = null;
    },

    async commit() {
      if (this.draft === value) { this.editing = false; return; }
      this.saving = true;
      this.error = null;
      try {
        const res = await fetch(patchUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
          body: JSON.stringify({ field: fieldName, value: this.draft }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          this.error = data.error || "Erreur lors de l'enregistrement.";
        } else {
          value = this.draft;
          this.justSaved = true;
          setTimeout(() => { this.justSaved = false; }, 1200);
          this.$dispatch("saved", { label: "Enregistré" });
          this.editing = false;
        }
      } catch (e) {
        this.error = "Erreur lors de l'enregistrement.";
      } finally {
        this.saving = false;
      }
    },
  }));


  Alpine.data("imageUpload", (currentUrl, uploadUrl, fieldName) => {
    let uploadController = null;
    return {
      preview: currentUrl || null,
      dragOver: false,
      err: null,
      uploading: false,

      onDrop(e) {
        this.dragOver = false;
        const file = e.dataTransfer?.files?.[0];
        if (file) this.handleFile(file);
      },

      async handleFile(file) {
        if (!file) return;
        this.err = null;
        if (!/^image\//.test(file.type)) { this.err = "Format d'image non supporté."; return; }
        if (file.size > 5 * 1024 * 1024) { this.err = "Fichier trop volumineux (5 Mo max)."; return; }

        if (uploadController) uploadController.abort();
        uploadController = new AbortController();
        this.uploading = true;
        try {
          const formData = new FormData();
          formData.append(fieldName, file);
          const res = await fetch(uploadUrl, {
            method: "POST",
            headers: { "X-CSRFToken": getCsrfToken() },
            body: formData,
            signal: uploadController.signal,
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          this.preview = data.url;
          this.$dispatch("saved", { label: "Image enregistrée" });
        } catch (e) {
          if (e.name !== "AbortError") this.err = "Erreur lors de l'envoi.";
        } finally {
          this.uploading = false;
        }
      },

      async remove() {
        this.uploading = true;
        this.err = null;
        try {
          const res = await fetch(uploadUrl, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
            body: JSON.stringify({ [fieldName]: null }),
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          this.preview = null;
          this.$dispatch("saved", { label: "Image retirée" });
        } catch (e) {
          this.err = "Erreur lors de la suppression.";
        } finally {
          this.uploading = false;
        }
      },
    };
  });


  Alpine.data("confirmDelete", (deleteUrl, requireTyping = null) => ({
    open: false,
    typed: "",
    deleting: false,

    get isDisabled() {
      return requireTyping ? this.typed.trim() !== requireTyping : false;
    },

    openModal() { this.typed = ""; this.open = true; },
    close() { this.open = false; },

    async confirm() {
      if (this.isDisabled) return;
      this.deleting = true;
      try {
        // Server must return JSON { "redirect_url": "/path/" } on success.
        const res = await fetch(deleteUrl, {
          method: "DELETE",
          headers: { "X-CSRFToken": getCsrfToken() },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.$dispatch("saved", { label: "Supprimé" });
        if (data.redirect_url) window.location.href = data.redirect_url;
      } catch (e) {
        this.deleting = false;
        this.open = false;
      }
    },
  }));


  Alpine.data("editModal", (editUrl) => ({
    open: false,
    errors: {},
    saving: false,

    openModal() { this.errors = {}; this.open = true; },
    close() { this.open = false; this.errors = {}; },

    fieldErrors(name) { return this.errors[name] || []; },

    async submit(form) {
      this.saving = true;
      this.errors = {};
      try {
        const res = await fetch(editUrl, {
          method: "POST",
          headers: { "X-CSRFToken": getCsrfToken() },
          body: new FormData(form),
        });
        const data = await res.json();
        if (res.ok) {
          window.location.href = data.redirect_url;
        } else {
          this.errors = data.errors || {};
        }
      } catch (e) {
        this.errors = { __all__: ["Erreur lors de l'enregistrement."] };
      } finally {
        this.saving = false;
      }
    },
  }));


  Alpine.data("savedBanner", () => {
    let timer = null;
    return {
      visible: false,
      message: "Enregistré",

      show(label) {
        this.message = label || "Enregistré";
        this.visible = true;
        clearTimeout(timer);
        timer = setTimeout(() => { this.visible = false; }, 2000);
      },

      hide() {
        clearTimeout(timer);
        this.visible = false;
      },
    };
  });

});
