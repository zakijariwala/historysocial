/* history-social review queue.
 *
 * One file, ES5, no modules, no dependencies. The page must work opened from a
 * plain static file server.
 *
 * Ported from the hadith-social review surface. Two rules here are load-bearing
 * and were paid for in bugs:
 *
 *   1. Nothing record-derived ever reaches the DOM through innerHTML. Captions
 *      and labels carry quotation marks and Arabic. innerHTML appears twice in
 *      this file and neither takes record data.
 *   2. The copy handler is synchronous and the caption is already on the
 *      button's dataset before the tap. iOS Safari only honours
 *      clipboard.writeText inside a tap handler with no await in front of it.
 *      Do not make it async. See DECISIONS.md #18.
 */
(function () {
  "use strict";

  var FLAG_KEY = "history.flags.v1";

  var state = {
    posts: [],
    activePost: null,
    activeSlide: 0,
    flags: {}
  };

  // ---------------------------------------------------------------- storage

  function loadFlags() {
    try {
      return JSON.parse(localStorage.getItem(FLAG_KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  function saveFlags() {
    try {
      localStorage.setItem(FLAG_KEY, JSON.stringify(state.flags));
    } catch (e) {
      /* Private mode, or storage full. The app still works; the ticks simply
         do not survive a reload. Not worth interrupting the reviewer over. */
    }
  }

  function flagsFor(id) {
    if (!state.flags[id]) state.flags[id] = { draft: false, posted: false };
    return state.flags[id];
  }

  /* posted_on is the durable signal, written in the database. The local tick
     is advisory. Either one counts. */
  function isPosted(post) {
    return !!post.posted_on || flagsFor(post.id).posted;
  }

  // ------------------------------------------------------------------ cards

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  function flagPair(post, name) {
    var pair = el("span", "flag-pair");
    var box = document.createElement("input");
    box.type = "checkbox";
    box.className = "flag-box";
    box.id = "flag-" + name + "-" + post.id;
    box.checked = name === "posted" ? isPosted(post) : flagsFor(post.id)[name];
    if (name === "posted" && post.posted_on) box.disabled = true;

    var label = el("label", "flag", name);
    label.setAttribute("for", box.id);

    box.addEventListener("click", function (ev) { ev.stopPropagation(); });
    label.addEventListener("click", function (ev) { ev.stopPropagation(); });

    box.addEventListener("change", function () {
      flagsFor(post.id)[name] = box.checked;
      saveFlags();
      if (name === "posted") {
        // Moves the card between sections, so the panels must be rebuilt.
        renderPanels();
      } else {
        // Only restyles in place. Rebuilding here would destroy the checkbox
        // just clicked and drop focus and scroll for no visible change.
        var card = document.getElementById("card-" + post.id);
        if (card) card.className = "card" + (box.checked ? " is-draft" : "");
      }
    });

    pair.appendChild(box);
    pair.appendChild(label);
    return pair;
  }

  function renderCard(post) {
    var card = el("div", "card" + (flagsFor(post.id).draft ? " is-draft" : ""));
    card.id = "card-" + post.id;

    card.appendChild(el("div", "imam", post.title));
    if (post.label) card.appendChild(el("div", "label", post.label));

    var bits = [post.pillar, post.ink, post.slides.length + " slides", post.status];
    if (post.occasion && post.occasion !== "normal") bits.splice(2, 0, post.occasion);
    card.appendChild(el("div", "meta", bits.join(" · ")));

    var flags = el("div", "flags");
    flags.appendChild(flagPair(post, "draft"));
    flags.appendChild(flagPair(post, "posted"));
    card.appendChild(flags);

    card.addEventListener("click", function () { openPost(post); });
    return card;
  }

  function fill(panel, posts, emptyText) {
    panel.innerHTML = "";          // no record data
    if (!posts.length) {
      panel.appendChild(el("div", "empty", emptyText));
      return;
    }
    for (var i = 0; i < posts.length; i++) panel.appendChild(renderCard(posts[i]));
  }

  function renderPanels() {
    var unposted = [], posted = [], i;
    for (i = 0; i < state.posts.length; i++) {
      (isPosted(state.posts[i]) ? posted : unposted).push(state.posts[i]);
    }
    fill(document.getElementById("unposted"), unposted, "Nothing waiting.");
    fill(document.getElementById("posted"), posted, "Nothing posted yet.");
    document.getElementById("count-unposted").textContent = unposted.length;
    document.getElementById("count-posted").textContent = posted.length;
  }

  function visiblePosts() {
    var tab = document.querySelector(".tab.active").dataset.tab;
    var out = [];
    for (var i = 0; i < state.posts.length; i++) {
      var p = state.posts[i];
      if ((tab === "posted") === isPosted(p)) out.push(p);
    }
    return out;
  }

  // ----------------------------------------------------------------- viewer

  function updateViewer() {
    var post = state.activePost;
    if (!post) return;
    document.getElementById("viewer-img").src = "data/" + post.slides[state.activeSlide];
    document.getElementById("viewer-count").textContent =
      post.slides.length < 2 ? "" : (state.activeSlide + 1) + "/" + post.slides.length;
  }

  function openPost(post) {
    state.activePost = post;
    state.activeSlide = 0;

    var dl = document.getElementById("download-all");
    if (post.zip) {
      dl.href = "data/" + post.zip;
      dl.classList.remove("hidden");
    } else {
      // Preview builds ship no zips. Hide the link rather than leave it at a 404.
      dl.removeAttribute("href");
      dl.classList.add("hidden");
    }

    var caption = post.caption === null || post.caption === undefined ? "" : post.caption;
    document.getElementById("copy-caption").dataset.caption = caption;
    document.getElementById("caption-text").textContent =
      caption || "No caption for this record.";

    document.getElementById("post-view").classList.remove("hidden");
    updateViewer();
  }

  function closePost() {
    state.activePost = null;
    document.getElementById("post-view").classList.add("hidden");
  }

  function step(delta) {
    var post = state.activePost;
    if (!post) return;
    var n = post.slides.length;
    state.activeSlide = ((state.activeSlide + delta) % n + n) % n;   // wraps
    updateViewer();
  }

  function stepPost(delta) {
    var list = visiblePosts();
    if (!list.length) return;
    var at = state.activePost ? list.indexOf(state.activePost) : -1;
    var next = at < 0 ? 0 : at + delta;
    if (next < 0 || next >= list.length) return;                     // stops
    openPost(list[next]);
  }

  // ------------------------------------------------------------------- wire

  function wire() {
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener("click", function (ev) {
        var name = ev.currentTarget.dataset.tab;
        var all = document.querySelectorAll(".tab");
        for (var j = 0; j < all.length; j++) {
          all[j].classList.toggle("active", all[j].dataset.tab === name);
        }
        document.getElementById("unposted").classList.toggle("active", name === "unposted");
        document.getElementById("posted").classList.toggle("active", name === "posted");
      });
    }

    document.getElementById("close-post").addEventListener("click", closePost);
    document.getElementById("prev-slide").addEventListener("click", function (ev) {
      ev.stopPropagation(); step(-1);
    });
    document.getElementById("next-slide").addEventListener("click", function (ev) {
      ev.stopPropagation(); step(1);
    });

    // Synchronous on purpose. Do not add await in front of writeText.
    document.getElementById("copy-caption").addEventListener("click", function (ev) {
      var button = ev.currentTarget;
      navigator.clipboard.writeText(button.dataset.caption || "");
      button.textContent = "Copied";
      setTimeout(function () { button.textContent = "COPY CAPTION"; }, 1500);
    });

    document.addEventListener("keydown", function (ev) {
      if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
      var open = !!state.activePost;
      switch (ev.key) {
        case "ArrowLeft":  if (open) { ev.preventDefault(); step(-1); } break;
        case "ArrowRight": if (open) { ev.preventDefault(); step(1); } break;
        case "ArrowUp":    ev.preventDefault(); stepPost(-1); break;
        case "ArrowDown":  ev.preventDefault(); stepPost(1); break;
        case "Home":       if (open) { ev.preventDefault(); state.activeSlide = 0; updateViewer(); } break;
        case "End":        if (open) { ev.preventDefault(); state.activeSlide = state.activePost.slides.length - 1; updateViewer(); } break;
        case "Escape":     if (open) closePost(); break;
        case "Enter":
          if (!open) {
            var list = visiblePosts();
            if (list.length) { ev.preventDefault(); openPost(list[0]); }
          }
          break;
      }
    });
  }

  // ------------------------------------------------------------------ start

  function start() {
    state.flags = loadFlags();
    wire();

    fetch("data/index.json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .catch(function () { return []; })
      .then(function (posts) {
        state.posts = Array.isArray(posts) ? posts : [];
        renderPanels();
      });

    // Absence is the normal case, not an error.
    fetch("data/meta.json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (meta) {
        if (meta && meta.unreviewed) {
          var banner = document.getElementById("review-banner");
          banner.textContent = meta.note || "Unreviewed preview build.";
          banner.classList.remove("hidden");
        }
      })
      .catch(function () { /* no meta.json: a production build */ });
  }

  start();
})();
