const root = document.documentElement;
const THEME_KEY = "unkubed-theme";
const MANUAL_KEY = "unkubed-theme-manual";

function applyTheme(theme) {
  root.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
}

function initThemeToggle() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) {
    applyTheme(saved);
  } else {
    applyTheme("light");
  }

  const toggle = document.getElementById("themeToggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      localStorage.setItem(MANUAL_KEY, "1");
    });
  }

  if (!localStorage.getItem(MANUAL_KEY)) {
    detectSunsetTheme();
  }
}

function detectSunsetTheme() {
  if (!navigator.geolocation) {
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const { latitude, longitude } = position.coords;
      fetch(
        `https://api.sunrise-sunset.org/json?lat=${latitude}&lng=${longitude}&formatted=0`
      )
        .then((response) => response.json())
        .then((data) => {
          const sunset = new Date(data.results.sunset);
          const now = new Date();
          if (now >= sunset) {
            applyTheme("dark");
          } else {
            const timeout = sunset.getTime() - now.getTime();
            window.setTimeout(() => applyTheme("dark"), timeout);
          }
        })
        .catch(() => {});
    },
    () => {}
  );
}

document.addEventListener("DOMContentLoaded", initThemeToggle);
