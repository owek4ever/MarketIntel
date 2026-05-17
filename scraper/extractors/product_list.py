"""
product_list.py — BaseExtractor ABC + HeuristicExtractor + PlatformHintAdapter.

This module hosts product list extraction logic and can be used directly
or via ProductListDetector.
"""

from __future__ import annotations

from typing import List
from playwright.async_api import Page
    


async def extract_product_list_items(
    page: Page, extract_from_schema_org: bool = False
) -> List[str]:
    if extract_from_schema_org:
        urls = []
        schemas = await page.evaluate(
            """() => Array.from(document.querySelectorAll("script[type='application/ld+json']")).map(src => JSON.parse(src.innerText))"""
        )
        for schema in schemas:
            if schema.get("@type") == "ItemList" and "itemListElement" in schema:
                items = []
                for element in schema["itemListElement"]:
                    if isinstance(element, dict):
                        url = element.get("url") or element.get("item", {}).get("url")
                        if url:
                            items.append(url)
                if items:
                    return items
            if schema.get("@type") == "Product":
                url = schema.get("url")
                if url:
                    urls.append(url)
                elif "offers" in schema and isinstance(schema["offers"], dict):
                    url = schema["offers"].get("url")
                    if url:
                        urls.append(url)
        if urls:
            return urls

    # get all elements with [itemtype*="schema.org/Product"]
    # product_elements = await page.locator('[itemtype*="schema.org/Product"]').all()

    links = await page.evaluate("""
() => {
function isElementInViewport(el) {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

let pattern = /(ajouter|acheter|lire la suite|Choisir des options|épuisé|epuise|fiche technique|choix des options|plus de détail|add to cart|sold out|sur command|en précommande|chariot|feuilleter|ref|réf|(\\d+\\s)?\\d+[,.]?\\d+(\\s)?(TND|DT|د.ت)|(\\d+\\s)?\\d+[,.]?\\d+&nbsp;(TND|DT)|\bstock\b)/i;

let anchors = document.querySelectorAll("a[href], button, span, p, h3, h4, h5, h6");
let res = [];

anchors.forEach(el => {
    if ((pattern.test(el.innerText) || pattern.test(el.textContent)) && isElementInViewport(el) && !el.closest(`header, footer, nav, .nav, [class*=navbar], .navbar, .topbar, .menu, .navigation, .breadcrumb`)) {
        res.push(el);
    }
});

let productUrls = new Set();

res.forEach(el => {
    if (/fiche technique|feuilleter|plus de détail[s]?|détail[s]?/i.test(el.textContent)) {
        if (!el.hasAttribute("href")) return;
        let href = el.getAttribute("href");
        if (href !== "" && !/[#?]/.test(href)) productUrls.add(href);
    }
})


let selectors =  ["h1 a, h2 a, h3 a, h4 a, h5 a, h6 a", "a:has(> h1), a:has(> h2), a:has(> h3)", "a[title]:has(img), a[href]:has(img[title])", "a:has(> div h6), a:has(img, span)"];
let linksForEachSelector = selectors.map(() => [])

selectors.forEach((sel, i) => {
    res.forEach(el => {
        let parent = el.parentElement;
        let url = [];

        while (parent && parent.getBoundingClientRect().width + 50 < window.innerWidth && url.length === 0) {
            let anchorAsHeading = parent.querySelector("a[title]");

            if (anchorAsHeading) {
                if (
                    !/[?#]/i.test(anchorAsHeading.getAttribute("href")) &&
                    anchorAsHeading.getAttribute("title") === anchorAsHeading.innerText
                ) {
                    url = [anchorAsHeading];
                    break;
                }
            }

            url = parent.querySelectorAll(sel)
            parent = parent.parentElement;
        }

        url.forEach(u => {
            if (!u.hasAttribute("href")) return;
            let href = u.getAttribute("href");
            if (href !== "" && !/[#?]/.test(href)) {
                linksForEachSelector[i].push(href)
            }
        });
    });
})

linksForEachSelector.push(Array.from(productUrls))
return linksForEachSelector.map(a => Array.from(new Set(a))).sort((a, b) => b.length - a.length)[0]
}
""")
    return links
