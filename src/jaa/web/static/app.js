/**
 * UI helpers - no innerHTML; highlights use text nodes only.
 */
(function () {
  "use strict";

  function highlightTerms(root, terms) {
    if (!root || !terms || !terms.length) {
      return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode);
    }
    const pattern = terms
      .filter(Boolean)
      .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
      .join("|");
    if (!pattern) {
      return;
    }
    const re = new RegExp("(" + pattern + ")", "gi");
    textNodes.forEach((node) => {
      const text = node.nodeValue;
      if (!text || !re.test(text)) {
        return;
      }
      re.lastIndex = 0;
      const parts = text.split(re);
      if (parts.length < 2) {
        return;
      }
      const parent = node.parentNode;
      if (!parent) {
        return;
      }
      const frag = document.createDocumentFragment();
      parts.forEach((part, i) => {
        if (!part) {
          return;
        }
        if (i % 2 === 1) {
          const mark = document.createElement("mark");
          mark.className = "highlight";
          mark.textContent = part;
          frag.appendChild(mark);
        } else {
          frag.appendChild(document.createTextNode(part));
        }
      });
      parent.replaceChild(frag, node);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-highlight-terms]").forEach((el) => {
      const raw = el.getAttribute("data-highlight-terms");
      if (!raw) {
        return;
      }
      try {
        const terms = JSON.parse(raw);
        if (Array.isArray(terms)) {
          highlightTerms(el, terms);
        }
      } catch (_err) {
        /* ignore malformed attribute */
      }
    });
  });
})();
