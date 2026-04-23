/**
 * Alpine.js components for Edito.
 *
 * Loaded deferred from base.html. Each component is registered on
 * document.addEventListener('alpine:init', ...) so Alpine can discover them.
 *
 * Global event contract
 * ---------------------
 * Successful mutations dispatch a 'saved' custom event on the component
 * element (bubbles to window). The savedBanner() component mounted on <body>
 * listens with @saved.window and shows a confirmation message.
 * Event detail: { label: string }  (optional — savedBanner falls back to "Enregistré")
 */

// ---------- CSRF helper ----------

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? match[1] : "";
}

// ---------- Component definitions ----------

document.addEventListener("alpine:init", () => {

  /**
   * inlineEdit(value, patchUrl, fieldName, inputType)
   *
   * Inline-edit component. Click display span to enter edit mode;
   * confirm with Enter (or Cmd/Ctrl+Enter for textarea), cancel with Escape.
   * On success PATCHes JSON { [fieldName]: draft } and dispatches 'saved'.
   */
  Alpine.data("inlineEdit", (value, patchUrl, fieldName, inputType = "text") => ({
    editing: false,
    draft: value,
    type: inputType,
    saving: false,
    justSaved: false,
    error: null,

    startEdit() {
      this.editing = true;
      this.$nextTick(() => {
        const ref =
          this.type === "textarea" ? this.$refs.inputTextarea :
          this.type === "select"   ? this.$refs.inputSelect   :
                                     this.$refs.inputText;
        if (ref) {
          ref.focus();
          if (ref.select) ref.select();
        }
      });
    },

    cancel() {
      this.draft = value;
      this.editing = false;
      this.error = null;
    },

    async commit() {
      if (this.draft === value) {
        this.editing = false;
        return;
      }
      this.saving = true;
      this.error = null;
      try {
        const res = await fetch(patchUrl, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ [fieldName]: this.draft }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        value = this.draft;
        this.justSaved = true;
        setTimeout(() => { this.justSaved = false; }, 1200);
        this.$dispatch("saved", { label: "Enregistré" });
      } catch (e) {
        this.error = "Erreur lors de l'enregistrement.";
      } finally {
        this.saving = false;
        this.editing = false;
      }
    },
  }));


  /**
   * imageUpload(currentUrl, uploadUrl, fieldName)
   *
   * Drag-drop + click file upload. Validates type (image/*) and size (≤5 MB).
   * POSTs a FormData with formData.append(fieldName, file) to uploadUrl.
   * Server should return JSON { url: "..." } with the stored file URL.
   * On remove, PATCHes { [fieldName]: null } to uploadUrl.
   * Dispatches 'saved' on success.
   */
  Alpine.data("imageUpload", (currentUrl, uploadUrl, fieldName) => ({
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
      if (!/^image\//.test(file.type)) {
        this.err = "Format d'image non supporté.";
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        this.err = "Fichier trop volumineux (5 Mo max).";
        return;
      }
      this.uploading = true;
      try {
        const formData = new FormData();
        formData.append(fieldName, file);
        const res = await fetch(uploadUrl, {
          method: "POST",
          headers: { "X-CSRFToken": getCsrfToken() },
          body: formData,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.preview = data.url;
        this.$dispatch("saved", { label: "Image enregistrée" });
      } catch (e) {
        this.err = "Erreur lors de l'envoi.";
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
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
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
  }));


  /**
   * confirmDelete(deleteUrl, requireTyping)
   *
   * Confirm-delete modal. requireTyping is an optional string the user must
   * retype verbatim before the confirm button is enabled.
   * On confirm, sends DELETE to deleteUrl and redirects to the JSON response
   * field "redirect_url".
   *
   * Server contract: DELETE deleteUrl → JSON { "redirect_url": "/path/" }
   */
  Alpine.data("confirmDelete", (deleteUrl, requireTyping = null) => ({
    open: false,
    typed: "",
    deleting: false,

    get isDisabled() {
      return requireTyping ? this.typed.trim() !== requireTyping : false;
    },

    openModal() {
      this.typed = "";
      this.open = true;
    },

    close() {
      this.open = false;
    },

    async confirm() {
      if (this.isDisabled) return;
      this.deleting = true;
      try {
        const res = await fetch(deleteUrl, {
          method: "DELETE",
          headers: { "X-CSRFToken": getCsrfToken() },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.$dispatch("saved", { label: "Supprimé" });
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        }
      } catch (e) {
        this.deleting = false;
        this.open = false;
      }
    },
  }));


  /**
   * savedBanner()
   *
   * Global success banner. Mount once on a persistent ancestor (e.g. <body>).
   * Listen with @saved.window="show($event.detail?.label)".
   * Auto-hides after 2 s.
   */
  Alpine.data("savedBanner", () => ({
    visible: false,
    message: "Enregistré",
    _timer: null,

    show(label) {
      this.message = label || "Enregistré";
      this.visible = true;
      clearTimeout(this._timer);
      this._timer = setTimeout(() => { this.visible = false; }, 2000);
    },

    hide() {
      clearTimeout(this._timer);
      this.visible = false;
    },
  }));

});
