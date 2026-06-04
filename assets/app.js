// Progressive enhancement for the static training site:
//  1. one-click "Copy" button on every code block
//  2. mobile navigation toggle
(function () {
  "use strict";

  // ---- Copy buttons on code blocks ----
  document.querySelectorAll("div.codehilite").forEach(function (block) {
    var pre = block.querySelector("pre");
    if (!pre) return;
    var btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      var code = pre.innerText;
      navigator.clipboard.writeText(code).then(function () {
        btn.textContent = "Copied";
        btn.classList.add("copied");
        setTimeout(function () {
          btn.textContent = "Copy";
          btn.classList.remove("copied");
        }, 1400);
      }).catch(function () {
        btn.textContent = "Press Ctrl+C";
      });
    });
    block.appendChild(btn);
  });

  // ---- Mobile nav toggle ----
  var toggle = document.getElementById("navToggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      document.body.classList.toggle("nav-open");
    });
  }
  // Close the drawer after picking a day on mobile.
  document.querySelectorAll(".sidebar a").forEach(function (a) {
    a.addEventListener("click", function () {
      document.body.classList.remove("nav-open");
    });
  });
})();
