document.documentElement.classList.add("admin-ui-ready");

/* ── Staggered panel entrance animations ── */
const panels = document.querySelectorAll(".admin-panel");
panels.forEach((panel, i) => {
  panel.style.animationDelay = `${i * 0.06}s`;
});

/* ── Service Control live polling ── */
const serviceControlRoot = document.querySelector("[data-admin-service-control='true']");

if (serviceControlRoot) {
  const feedbackNode = document.querySelector("[data-admin-feedback]");
  const statusFields = new Map(
    Array.from(document.querySelectorAll("[data-admin-status-field]")).map((node) => [
      node.dataset.adminStatusField,
      node,
    ]),
  );
  const actionForms = Array.from(document.querySelectorAll("[data-admin-action-form]"));
  let pollTimer = null;

  const renderStatus = (status) => {
    for (const [key, node] of statusFields.entries()) {
      if (!(key in status)) {
        continue;
      }
      const value = status[key];
      node.textContent = value === null ? "Not running" : String(value);
    }
  };

  const setFeedback = (message, isError = false) => {
    if (!feedbackNode) {
      return;
    }
    feedbackNode.hidden = false;
    feedbackNode.textContent = message;
    feedbackNode.dataset.adminFeedbackState = isError ? "error" : "success";
  };

  const pollStatus = async () => {
    const response = await fetch("/admin/service-control/status", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error("Failed to refresh service status.");
    }
    renderStatus(await response.json());
  };

  const startPolling = (intervalMs) => {
    window.clearInterval(pollTimer);
    pollTimer = window.setInterval(() => {
      pollStatus().catch((error) => setFeedback(error.message, true));
    }, intervalMs);
  };

  actionForms.forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const action = form.querySelector("[data-admin-action]")?.dataset.adminAction ?? "action";

      try {
        const response = await fetch(form.action, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || `Failed to ${action}.`);
        }
        renderStatus(body.status);
        setFeedback(body.result.message || `${action} completed.`);
        if (body.detached && body.poll_url) {
          startPolling(1000);
        } else {
          startPolling(5000);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : `Failed to ${action}.`;
        setFeedback(message, true);
      }
    });
  });

  pollStatus().catch(() => undefined);
  startPolling(5000);
}
