document.addEventListener("DOMContentLoaded", () => {
  // Проверяем, загружен ли hls.js
  const HlsCtor = globalThis.Hls;
  if (!HlsCtor) {
    console.error("Hls.js не загружен");
    return;
  }

  const video = document.getElementById("video");
  if (!video) {
    console.error("Элемент <video> не найден");
    return;
  }

  // Формируем URL относительно origin, чтобы всегда сохранялся текущий порт (например, :8082).
  const streamUrl = new URL('/hls/stream.m3u8', window.location.origin).toString();
  let hls = null;

  function initPlayer(url) {
    if (!url) return;

    // Chrome / Firefox / Edge
    if (HlsCtor.isSupported()) {
      hls = new HlsCtor();
      hls.loadSource(url);
      hls.attachMedia(video);

      hls.on(HlsCtor.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {
          console.warn("Автовоспроизведение запрещено браузером");
        });
      });

      hls.on(HlsCtor.Events.ERROR, (event, data) => {
        console.error("HLS error:", data);
      });

      return;
    }

    // Safari / iOS
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = url;
      video.addEventListener("loadedmetadata", () => {
        video.play().catch(() => {
          console.warn("Автовоспроизведение запрещено браузером");
        });
      });
      video.addEventListener("error", (e) => console.error("Video error:", e));
      return;
    }

    alert("Ваш браузер не поддерживает HLS");
  }

  initPlayer(streamUrl);
});
