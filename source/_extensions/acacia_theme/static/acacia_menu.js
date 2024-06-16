/**
 * Acacia documentation's mobile menu
 */

function acaciaMenuUpdate() {
    const menu = document.getElementById("mobile-menu-wrapper");
    const toggle = document.getElementById("menu-toggle");
    const expanded = toggle.classList.contains("pressed");
    menu.style.left = expanded ?
        "0" : "calc(-1 * var(--sidebar-width) - 10px)";
    toggle.textContent = expanded ?
        // "\xd7" : "\u2630";
        "<" : ">";
}

function acaciaMenuToggle() {
    document.getElementById("menu-toggle").classList.toggle("pressed");
    window.requestAnimationFrame(acaciaMenuUpdate);
}

document.addEventListener("DOMContentLoaded", function () {
    // Initial update
    acaciaMenuUpdate();
    // Close menu when a link on the menu is clicked
    const menu = document.getElementById("mobile-menu");
    menu.addEventListener("click", function (event) {
        if (event.target.tagName.toLowerCase() === "a") {
            acaciaMenuToggle();
        }
    })
    // Close menu when body is clicked
    const body = document.getElementsByClassName("document")[0];
    const toggle = document.getElementById("menu-toggle");
    body.addEventListener("click", function () {
        if (toggle.classList.contains("pressed")) {
            acaciaMenuToggle();
        }
    })
});
