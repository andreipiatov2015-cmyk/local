// Настройка/запуск/остановка трансляции в VK/OK — модалка раньше жила на
// странице "Участники очного этапа" (admin.html), которая была удалена как
// избыточная (участники теперь через "Таблицы заявок"). Модалка перенесена
// на "Мероприятие" — теперь главную страницу после входа.
function initVkBroadcast() {
  const vkStreamButton = document.getElementById("vkStreamButton");
  const vkModal = document.getElementById("vkModal");
  const vkCloseBtn = document.getElementById("vkCloseBtn");
  const vkScheduleBtn = document.getElementById("vkScheduleBtn");
  const vkStopBtn = document.getElementById("vkStopBtn");
  const vkTabs = document.querySelectorAll(".vk-tab");
  const vkTabPanels = document.querySelectorAll(".vk-tab-panel");

  const vkPreviewVideo = document.getElementById("vkPreviewVideo");
  const vkPreviewImage = document.getElementById("vkPreviewImage");
  const vkImageInput = document.getElementById("vkImage");

  const vkTargetName = document.getElementById("vkTargetName");
  const vkTargetUrl = document.getElementById("vkTargetUrl");
  const vkAddTargetBtn = document.getElementById("vkAddTargetBtn");
  const vkTargetsList = document.getElementById("vkTargetsList");
  const vkTargetsEmpty = document.getElementById("vkTargetsEmpty");
  const vkBroadcastModal = document.getElementById("vkBroadcastModal");
  const vkBroadcastList = document.getElementById("vkBroadcastList");
  const vkBroadcastNotice = document.getElementById("vkBroadcastNotice");
  const vkBroadcastConfirm = document.getElementById("vkBroadcastConfirm");
  const vkBroadcastCancel = document.getElementById("vkBroadcastCancel");
  const vkBroadcastClose = document.getElementById("vkBroadcastClose");

  if (!vkStreamButton || !vkModal) return; // страница без VK-модалки

  let streamUrl = "";
  let vkTargets = [];
  let selectedTargetId = null;
  let hlsInstance = null;
  let lastVkPreviewUrl = "";

  function stopVkPreviewPlayer() {
    if (!vkPreviewVideo) return;
    if (hlsInstance) {
      hlsInstance.destroy();
      hlsInstance = null;
    }
    vkPreviewVideo.pause();
    vkPreviewVideo.removeAttribute("src");
    vkPreviewVideo.load();
  }

  function setVkPreviewImage(url) {
    if (!vkPreviewImage) return;
    if (url) {
      lastVkPreviewUrl = url;
      vkPreviewImage.src = url;
      vkPreviewImage.classList.add("visible");
    } else {
      vkPreviewImage.classList.remove("visible");
    }
  }

  function showVkPreviewImage(url) {
    setVkPreviewImage(url || lastVkPreviewUrl);
    vkPreviewVideo?.classList.add("hidden");
  }

  function showVkPreviewVideo() {
    vkPreviewVideo?.classList.remove("hidden");
    vkPreviewImage?.classList.remove("visible");
  }

  function initVkPreviewPlayer(nextStreamUrl) {
    if (!vkPreviewVideo || !nextStreamUrl) {
      stopVkPreviewPlayer();
      showVkPreviewImage(lastVkPreviewUrl);
      return;
    }

    if (hlsInstance) {
      hlsInstance.destroy();
      hlsInstance = null;
    }

    const HlsCtor = globalThis.Hls;
    if (HlsCtor && HlsCtor.isSupported()) {
      hlsInstance = new HlsCtor();
      hlsInstance.loadSource(nextStreamUrl);
      hlsInstance.attachMedia(vkPreviewVideo);
      hlsInstance.on(HlsCtor.Events.ERROR, () => {
        stopVkPreviewPlayer();
        showVkPreviewImage(lastVkPreviewUrl);
      });
    } else if (vkPreviewVideo.canPlayType("application/vnd.apple.mpegurl")) {
      vkPreviewVideo.src = nextStreamUrl;
    }
    showVkPreviewVideo();
  }

  function renderBroadcastTargets() {
    if (!vkBroadcastList) return;
    vkBroadcastList.innerHTML = "";

    if (!vkTargets.length) {
      if (vkBroadcastNotice) {
        vkBroadcastNotice.textContent = "Нет сохраненных RTMP направлений.";
      }
      if (vkBroadcastConfirm) vkBroadcastConfirm.disabled = true;
      return;
    }

    vkTargets.forEach((target) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "vk-target vk-target-select";
      item.textContent = target.name || "Без названия";
      item.dataset.targetId = target.id;
      if (target.id === selectedTargetId) {
        item.classList.add("active");
        if (vkBroadcastNotice) {
          vkBroadcastNotice.textContent = `Начать трансляцию в ${target.name || "направление"}?`;
        }
      }
      item.addEventListener("click", () => {
        selectedTargetId = target.id;
        renderBroadcastTargets();
        if (vkBroadcastConfirm) vkBroadcastConfirm.disabled = false;
        if (vkBroadcastNotice) {
          vkBroadcastNotice.textContent = `Начать трансляцию в ${target.name || "направление"}?`;
        }
      });
      vkBroadcastList.appendChild(item);
    });

    if (vkBroadcastConfirm) vkBroadcastConfirm.disabled = !selectedTargetId;
  }

  function renderTargetsList() {
    if (!vkTargetsList) return;
    vkTargetsList.innerHTML = "";

    if (!vkTargets.length) {
      if (vkTargetsEmpty) {
        vkTargetsEmpty.textContent = "Серверы ещё не добавлены.";
      }
      return;
    }

    if (vkTargetsEmpty) vkTargetsEmpty.textContent = "";

    vkTargets.forEach((target) => {
      const row = document.createElement("div");
      row.className = "vk-target-row";

      const meta = document.createElement("div");
      meta.className = "vk-target-meta";

      const name = document.createElement("div");
      name.className = "vk-target-name";
      name.textContent = target.name || "Без названия";

      const url = document.createElement("div");
      url.className = "vk-target-url";
      url.textContent = target.url || "URL не указан";

      meta.appendChild(name);
      meta.appendChild(url);

      const actions = document.createElement("div");
      actions.className = "vk-actions";

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "btn btn-secondary";
      removeBtn.textContent = "Удалить";
      removeBtn.addEventListener("click", async () => {
        const resp = await fetch(`/stream/targets/${target.id}`, { method: "DELETE" });
        if (resp.ok) {
          await loadVkStatus();
          renderTargetsList();
          renderBroadcastTargets();
        }
      });

      actions.appendChild(removeBtn);
      row.appendChild(meta);
      row.appendChild(actions);
      vkTargetsList.appendChild(row);
    });
  }

  async function loadVkStatus() {
    const resp = await fetch("/vk/status");
    if (!resp.ok) return;

    const data = await resp.json();
    selectedTargetId = (data.target_ids || [])[0] || null;
    vkTargets = data.targets || [];
    streamUrl = data.stream_url || "";

    const titleInput = document.getElementById("vkTitle");
    if (titleInput) titleInput.value = data.title || "";

    if (data.preview_url) setVkPreviewImage(data.preview_url);
    if (streamUrl) {
      showVkPreviewVideo();
      initVkPreviewPlayer(streamUrl);
    } else {
      stopVkPreviewPlayer();
      showVkPreviewImage(data.preview_url || lastVkPreviewUrl);
    }

    renderTargetsList();
  }

  // Tabs switching
  vkTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      vkTabs.forEach((t) => t.classList.remove("active"));
      vkTabPanels.forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const key = tab.dataset.tab;
      document.querySelector(`.vk-tab-panel[data-panel="${key}"]`)?.classList.add("active");
    });
  });

  vkStreamButton?.addEventListener("click", (e) => {
    e.preventDefault();
    vkModal?.classList.add("visible");
    loadVkStatus();
  });

  vkImageInput?.addEventListener("change", async () => {
    const file = vkImageInput.files?.[0];
    if (!file) return;

    const form = new FormData();
    form.append("image", file);

    const resp = await fetch("/vk/preview", { method: "POST", body: form });
    if (resp.ok) {
      const data = await resp.json();
      if (data.preview_url) {
        setVkPreviewImage(data.preview_url);
        lastVkPreviewUrl = data.preview_url;
      }
    } else {
      alert("Не удалось сохранить превью.");
    }
  });

  vkCloseBtn?.addEventListener("click", () => {
    vkModal?.classList.remove("visible");
  });

  vkAddTargetBtn?.addEventListener("click", async () => {
    const name = vkTargetName?.value.trim() || "";
    if (!name) return;

    const resp = await fetch("/stream/targets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, url: vkTargetUrl?.value.trim() || "" }),
    });

    if (resp.ok) {
      if (vkTargetName) vkTargetName.value = "";
      if (vkTargetUrl) vkTargetUrl.value = "";
      await loadVkStatus();
      renderTargetsList();
    }
  });

  vkScheduleBtn?.addEventListener("click", async () => {
    await loadVkStatus();
    renderBroadcastTargets();
    vkBroadcastModal?.classList.add("visible");
  });

  vkStopBtn?.addEventListener("click", async () => {
    if (!confirm("Остановить трансляцию в VK/OK?")) return;
    const resp = await fetch("/vk/stop", { method: "POST" });
    if (resp.ok) {
      await loadVkStatus();
    } else {
      alert("Не удалось остановить трансляцию.");
    }
  });

  vkBroadcastClose?.addEventListener("click", () => {
    vkBroadcastModal?.classList.remove("visible");
  });

  vkBroadcastCancel?.addEventListener("click", () => {
    vkBroadcastModal?.classList.remove("visible");
  });

  vkBroadcastConfirm?.addEventListener("click", async () => {
    const title = document.getElementById("vkTitle")?.value || "";
    if (!selectedTargetId) {
      alert("Выберите направление трансляции.");
      return;
    }

    const resp = await fetch("/vk/start_now", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, target_ids: [selectedTargetId] }),
    });

    if (resp.ok) {
      vkBroadcastModal?.classList.remove("visible");
      vkModal?.classList.remove("visible");
    } else {
      alert("Ошибка старта.");
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initVkBroadcast);
} else {
  initVkBroadcast();
}
