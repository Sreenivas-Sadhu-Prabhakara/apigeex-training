// app.js — progressive enhancement for the static training site:
//   1. one-click "Copy" on every code block
//   2. mobile navigation toggle
//   3. localStorage progress tracking (nav ticks + progress bar + "mark complete")
//   4. reading-progress bar
//   5. "On this page" TOC active-section highlighting
(function () {
  "use strict";

  var PROGRESS_KEY = "apigeex.progress.v1";
  var TOTAL_DAYS = 30;

  function getDone() {
    try { return JSON.parse(localStorage.getItem(PROGRESS_KEY)) || []; }
    catch (e) { return []; }
  }
  function setDone(arr) {
    arr = arr.filter(function (v, i, a) { return a.indexOf(v) === i; }).sort(function (a, b) { return a - b; });
    try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(arr)); } catch (e) {}
    return arr;
  }

  // ---- Copy buttons on code blocks ----
  document.querySelectorAll("div.codehilite").forEach(function (block) {
    var pre = block.querySelector("pre");
    if (!pre) return;
    var btn = document.createElement("button");
    btn.className = "copy-btn"; btn.type = "button"; btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(pre.innerText).then(function () {
        btn.textContent = "Copied"; btn.classList.add("copied");
        setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1400);
      }).catch(function () { btn.textContent = "Press Ctrl+C"; });
    });
    block.appendChild(btn);
  });

  // ---- Mobile nav toggle ----
  var toggle = document.getElementById("navToggle");
  if (toggle) toggle.addEventListener("click", function () { document.body.classList.toggle("nav-open"); });
  document.querySelectorAll(".sidebar a").forEach(function (a) {
    a.addEventListener("click", function () { document.body.classList.remove("nav-open"); });
  });

  // ---- Progress: reflect completion in the sidebar ----
  function refreshProgress() {
    var done = getDone();
    document.querySelectorAll(".sidebar li[data-day]").forEach(function (li) {
      var d = +li.getAttribute("data-day");
      li.classList.toggle("completed", done.indexOf(d) >= 0);
    });
    var fill = document.getElementById("navProgressFill");
    var text = document.getElementById("navProgressText");
    var pct = Math.round((done.length / TOTAL_DAYS) * 100);
    if (fill) fill.style.width = pct + "%";
    if (text) text.textContent = done.length + " / " + TOTAL_DAYS + " complete";
  }
  refreshProgress();

  // ---- "Mark complete" toggle on a day page ----
  var markBtn = document.getElementById("markComplete");
  var main = document.querySelector("main[data-day]");
  if (markBtn && main) {
    var day = +main.getAttribute("data-day");
    var sync = function () {
      var isDone = getDone().indexOf(day) >= 0;
      markBtn.parentNode.classList.toggle("is-done", isDone);
      markBtn.querySelector(".mark-box").innerHTML = isDone ? "&#10003;" : "&#10003;";
      markBtn.childNodes[markBtn.childNodes.length - 1].nodeValue =
        isDone ? (" Day " + (day < 10 ? "0" + day : day) + " complete") : (" Mark Day " + (day < 10 ? "0" + day : day) + " complete");
    };
    markBtn.addEventListener("click", function () {
      var done = getDone(), i = done.indexOf(day);
      if (i >= 0) done.splice(i, 1); else done.push(day);
      setDone(done); refreshProgress(); sync();
    });
    sync();
  }

  // ---- Reading-progress bar ----
  var bar = document.getElementById("readingBar");
  if (bar) {
    var onScroll = function () {
      var h = document.documentElement, b = document.body;
      var st = h.scrollTop || b.scrollTop;
      var sh = (h.scrollHeight || b.scrollHeight) - h.clientHeight;
      bar.style.width = (sh > 0 ? (st / sh) * 100 : 0) + "%";
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // ---- "On this page" active-section highlighting ----
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc-rail a"));
  if (tocLinks.length) {
    var targets = tocLinks.map(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1));
      return document.getElementById(id);
    });
    var spy = function () {
      var pos = window.scrollY + 120, idx = 0;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i] && targets[i].offsetTop <= pos) idx = i;
      }
      tocLinks.forEach(function (a, i) { a.classList.toggle("active", i === idx); });
    };
    window.addEventListener("scroll", spy, { passive: true });
    spy();
  }
})();
