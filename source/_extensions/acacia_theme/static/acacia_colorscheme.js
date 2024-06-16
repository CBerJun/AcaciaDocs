function acaciaSetColorScheme(colorScheme) {
    // Update media
    const f1 = document.getElementById("pygments_dark_css");
    const f2 = document.getElementById("acacia_dark_theme_css");
    localStorage.setItem("acaciaColorScheme", colorScheme);
    if (colorScheme === "auto") {
        f1.media = f2.media = "(prefers-color-scheme: dark)";
    }
    else if (colorScheme === "light") {
        f1.media = f2.media = "not all";
    }
    else if (colorScheme === "dark") {
        f1.media = f2.media = "all";
    }
    // Update toggle
    const themeSelectors = document.getElementsByClassName('theme-selector');
    [...themeSelectors].forEach(e => e.value = colorScheme);
}

document.addEventListener("DOMContentLoaded", function () {
    // Initial update
    acaciaSetColorScheme(localStorage.getItem("acaciaColorScheme") || "auto");
});
