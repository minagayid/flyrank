(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) return;
  var scriptUrl = new URL(script.src, document.baseURI);
  var widgetId = scriptUrl.searchParams.get("widget_id");
  var apiOrigin = scriptUrl.origin;
  var root = document.createElement("section");
  root.className = "fr-widget";
  root.setAttribute("aria-label", "Signup form");
  root.dataset.widgetId = widgetId || "";
  script.parentNode.insertBefore(root, script);
  var status = document.createElement("p");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.dataset.status = "";
  root.appendChild(status);
  var pendingSubmission = null;

  function message(text, kind) {
    status.textContent = text;
    status.dataset.kind = kind || "info";
  }

  function requestKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "lead-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  }

  function render(config) {
    root.classList.add("theme-" + (config.display.theme === "dark" ? "dark" : "light"));
    if (config.display.position === "floating") root.classList.add("position-floating");

    var title = document.createElement("h2");
    title.textContent = config.title;
    root.appendChild(title);
    if (config.description) {
      var description = document.createElement("p");
      description.textContent = config.description;
      root.appendChild(description);
    }

    var form = document.createElement("form");
    form.noValidate = false;
    config.fields.forEach(function (field) {
      var label = document.createElement("label");
      label.textContent = field.label;
      label.htmlFor = "fr-" + config.id + "-" + field.name;
      var input = document.createElement("input");
      input.id = label.htmlFor;
      input.name = field.name;
      input.type = field.type;
      input.maxLength = field.max_length;
      input.required = Boolean(field.required);
      input.autocomplete = field.type === "email" ? "email" : field.name === "name" ? "name" : "on";
      label.appendChild(input);
      form.appendChild(label);
    });

    var honeypot = document.createElement("input");
    honeypot.type = "text";
    honeypot.name = "company_website";
    honeypot.tabIndex = -1;
    honeypot.autocomplete = "off";
    honeypot.setAttribute("aria-hidden", "true");
    honeypot.className = "fr-honeypot";
    form.appendChild(honeypot);

    var button = document.createElement("button");
    button.type = "submit";
    button.textContent = config.button_text;
    form.appendChild(button);
    root.appendChild(form);

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      button.disabled = true;
      message("Sending…", "info");
      var values = {};
      config.fields.forEach(function (field) {
        var control = form.elements.namedItem(field.name);
        values[field.name] = control.value;
      });
      try {
        var serializedBody = JSON.stringify({
          widget_id: config.id,
          fields: values,
          company_website: honeypot.value
        });
        if (!pendingSubmission || pendingSubmission.body !== serializedBody) {
          pendingSubmission = { key: requestKey(), body: serializedBody };
        }
        var response = await fetch(apiOrigin + "/api/public/submissions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": pendingSubmission.key
          },
          body: pendingSubmission.body
        });
        var result = await response.json();
        if (!response.ok) {
          var detail = result && result.error && result.error.message;
          throw new Error(detail || "The form could not be sent. Please try again.");
        }
        pendingSubmission = null;
        message("Thanks. Your details were received.", "success");
        form.reset();
      } catch (error) {
        message(error.message || "A network problem interrupted the request. Please try again.", "error");
      } finally {
        button.disabled = false;
      }
    });
  }

  if (!widgetId) {
    message("This widget is missing its ID.", "error");
    return;
  }
  fetch(apiOrigin + "/api/public/widgets/" + encodeURIComponent(widgetId) + "/config")
    .then(function (response) {
      if (!response.ok) throw new Error("Widget configuration is unavailable.");
      return response.json();
    })
    .then(render)
    .catch(function () {
      message("This form is temporarily unavailable.", "error");
    });

  var style = document.createElement("style");
  style.textContent = ".fr-widget{box-sizing:border-box;max-width:28rem;padding:1.25rem;border:1px solid #cbd5d1;border-radius:.75rem;font:16px/1.45 system-ui,sans-serif;color:#17211e;background:#fff}.fr-widget *{box-sizing:border-box}.fr-widget h2{margin:0 0 .4rem;font-size:1.25rem}.fr-widget p{margin:.35rem 0 .8rem}.fr-widget form{display:grid;gap:.75rem}.fr-widget label{display:grid;gap:.3rem;font-weight:600}.fr-widget input{min-height:2.75rem;padding:.55rem .7rem;border:1px solid #8a9994;border-radius:.4rem;font:inherit}.fr-widget input:focus,.fr-widget button:focus{outline:3px solid #2f7a67;outline-offset:2px}.fr-widget button{min-height:2.75rem;padding:.55rem .8rem;border:0;border-radius:.4rem;background:#17634f;color:#fff;font:inherit;font-weight:700;cursor:pointer}.fr-widget button:disabled{opacity:.65;cursor:wait}.fr-widget [data-kind=error]{color:#9a2a1c}.fr-widget [data-kind=success]{color:#17634f}.fr-widget.theme-dark{background:#17211e;color:#f4f7f5;border-color:#62706b}.fr-widget.theme-dark input{background:#202c28;color:#fff}.fr-widget.position-floating{position:fixed;right:1rem;bottom:1rem;z-index:9999;box-shadow:0 12px 34px #0002}.fr-honeypot{position:absolute!important;left:-10000px!important;width:1px!important;height:1px!important;overflow:hidden!important}";
  document.head.appendChild(style);
})();
