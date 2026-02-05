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

  const streamUrl = "http://192.168.31.18:8080/hls/test.m3u8";
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
      return;
    }

    alert("Ваш браузер не поддерживает HLS");
  }

  initPlayer(streamUrl);
});
