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

  Alpine.data("inlineEdit", (value, patchUrl, fieldName, inputType = "text", options = [], requireConfirm = false) => ({
    editing: false,
    confirming: false,
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
      this.confirming = false;
      this.error = null;
    },

    async commit() {
      if (this.draft === value) { this.editing = false; return; }
      if (requireConfirm && !this.confirming) {
        this.confirming = true;
        return;
      }
      await this._save();
    },

    async confirmAndSave() {
      await this._save();
    },

    async _save() {
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
          this.confirming = false;
        } else {
          value = this.draft;
          this.justSaved = true;
          this.confirming = false;
          this.editing = false;
          setTimeout(() => { this.justSaved = false; }, 1200);
          this.$dispatch("saved", { label: "Enregistré" });
        }
      } catch (e) {
        this.error = "Erreur lors de l'enregistrement.";
        this.confirming = false;
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
        let data;
        try {
          data = await res.json();
        } catch {
          this.errors = { __all__: [`Erreur serveur (${res.status}).`] };
          return;
        }
        if (res.ok) {
          window.location.href = data.redirect_url;
        } else {
          this.errors = data.errors || { __all__: [data.error || `Erreur (${res.status}).`] };
        }
      } catch (e) {
        this.errors = { __all__: ["Erreur réseau."] };
      } finally {
        this.saving = false;
      }
    },
  }));


  Alpine.data("transitionConfirm", (transitionUrl, transitionName) => ({
    open: false,
    note: "",
    submitting: false,
    error: null,

    show() { this.open = true; this.note = ""; this.error = null; },
    cancel() { this.open = false; },

    async confirm() {
      this.submitting = true;
      this.error = null;
      try {
        const body = new URLSearchParams({ transition: transitionName, note: this.note });
        const res = await fetch(transitionUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCsrfToken(),
          },
          body,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          this.error = data.error || "Une erreur est survenue.";
          this.submitting = false;
          return;
        }
        window.location.href = data.redirect_url;
      } catch {
        this.error = "Erreur réseau.";
        this.submitting = false;
      }
    },
  }));


  Alpine.data("prefs", () => ({
    theme:    "chaleureuse",
    contrast: "normal",
    zoom:     "normal",
    open:     false,

    init() {
      const html = document.documentElement;
      this.theme    = html.getAttribute("data-theme")    || "chaleureuse";
      this.contrast = html.getAttribute("data-contrast") || "normal";
      this.zoom     = html.getAttribute("data-zoom")     || "normal";
    },

    applyPref(key, value) {
      this[key] = value;
      document.documentElement.setAttribute("data-" + key, value);
      try {
        const saved = JSON.parse(localStorage.getItem("edito-prefs") || "{}");
        saved[key] = value;
        localStorage.setItem("edito-prefs", JSON.stringify(saved));
      } catch (e) {}
    },
  }));



  Alpine.data("fileInput", () => ({
    fileName: null,
    isDragging: false,

    onFileChange(e) {
      const file = e.target.files[0] || null;
      this.fileName = file ? file.name : null;
    },

    onDrop(e) {
      this.isDragging = false;
      const file = e.dataTransfer.files[0] || null;
      if (file) {
        this.fileName = file.name;
        const input = this.$refs.fileInput;
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
      }
    },

    clear(e) {
      e.stopPropagation();
      this.fileName = null;
      this.$refs.fileInput.value = "";
    },
  }));

  Alpine.data("contactAutocomplete", ({ searchUrl, initialName = "", initialId = "" } = {}) => {
    let debounceTimer = null;
    return {
      query: initialName,
      selectedId: String(initialId),
      selectedName: initialName,
      results: [],
      open: false,
      loading: false,

      init() {
        this.$watch("query", (val) => {
          if (this.selectedId && val === this.selectedName) return;
          this.selectedId = "";
          this.selectedName = "";
          clearTimeout(debounceTimer);
          debounceTimer = setTimeout(() => this._search(val), 200);
        });
      },

      async _search(q) {
        if (!q.trim()) { this.results = []; this.open = false; return; }
        this.loading = true;
        try {
          const url = new URL(searchUrl, window.location.origin);
          url.searchParams.set("q", q);
          const res = await fetch(url);
          const data = await res.json();
          this.results = data.results || [];
          this.open = this.results.length > 0;
        } catch (_) {
          this.results = [];
          this.open = false;
        } finally {
          this.loading = false;
        }
      },

      select(item) {
        this.selectedId = String(item.id);
        this.selectedName = item.name;
        this.query = item.name;
        this.open = false;
        this.results = [];
      },

      onBlur() {
        setTimeout(() => { this.open = false; }, 150);
      },
    };
  });


  Alpine.data("calendarView", (todayStr) => {
    const events = JSON.parse(document.getElementById("calendar-events").textContent);
    const [todayYear, todayMonth0, todayDay] = todayStr.split("-").map(Number);
    const todayMonth = todayMonth0 - 1; // 0-based

    const todayAbs = todayYear * 12 + todayMonth;
    const minAbs = todayAbs - 6;
    const maxAbs = todayAbs + 12;
    const MAX_VISIBLE = 3;

    const eventsByDate = new Map();
    for (const evt of events) {
      if (!eventsByDate.has(evt.date)) eventsByDate.set(evt.date, []);
      eventsByDate.get(evt.date).push(evt);
    }

    function isoDate(d) {
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    }

    return {
      year: todayYear,
      month: todayMonth,
      expandedDate: null,

      get isCurrentMonth() { return this.year === todayYear && this.month === todayMonth; },
      get canPrev() { return this.year * 12 + this.month > minAbs; },
      get canNext() { return this.year * 12 + this.month < maxAbs; },

      get monthLabel() {
        return new Date(this.year, this.month, 1)
          .toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
      },

      prevMonth() {
        if (!this.canPrev) return;
        if (this.month === 0) { this.month = 11; this.year--; } else { this.month--; }
        this.expandedDate = null;
      },

      nextMonth() {
        if (!this.canNext) return;
        if (this.month === 11) { this.month = 0; this.year++; } else { this.month++; }
        this.expandedDate = null;
      },

      goToday() { this.year = todayYear; this.month = todayMonth; this.expandedDate = null; },

      toggleExpand(dateStr) {
        this.expandedDate = this.expandedDate === dateStr ? null : dateStr;
      },

      overflowCount(cell) { return cell.events.length - MAX_VISIBLE; },

      get cells() {
        const year = this.year;
        const month = this.month;
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const startDow = (new Date(year, month, 1).getDay() + 6) % 7; // Mon=0…Sun=6

        const cells = [];

        for (let i = startDow; i > 0; i--) {
          const d = new Date(year, month, 1 - i);
          cells.push({ day: d.getDate(), inMonth: false, isToday: false, dateStr: isoDate(d), events: [] });
        }

        for (let d = 1; d <= daysInMonth; d++) {
          const dateStr = isoDate(new Date(year, month, d));
          const isToday = (year === todayYear && month === todayMonth && d === todayDay);
          cells.push({ day: d, inMonth: true, isToday, dateStr, events: eventsByDate.get(dateStr) ?? [] });
        }

        const trailing = (7 - cells.length % 7) % 7;
        for (let d = 1; d <= trailing; d++) {
          const dt = new Date(year, month + 1, d);
          cells.push({ day: dt.getDate(), inMonth: false, isToday: false, dateStr: isoDate(dt), events: [] });
        }

        return cells;
      },
    };
  });


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
