document.addEventListener('DOMContentLoaded', () => {
    // Проверяем, доступна ли библиотека Hls
    if (typeof globalThis.Hls === 'undefined') {
        console.error('Hls.js не загружен!');
        return;
    }

    const video = document.getElementById('video');
    const streamUrl = 'http://192.168.31.18:8080/hls/test.m3u8';
    let hls = null;

    if (!video) {
        console.error('Элемент video не найден.');
        return;
    }

    // Проверяем, поддерживается ли HLS в текущем браузере
    if (globalThis.Hls.isSupported()) {
        hls = new globalThis.Hls();

        // Укажите URL вашего HLS-потока (файл .m3u8)
        hls.loadSource(streamUrl);

        // Подключаем HLS к видеоплееру
        hls.attachMedia(video);

        // Запускаем воспроизведение, когда поток готов
        hls.on(globalThis.Hls.Events.MANIFEST_PARSED, () => {
            video.play().catch(e => {
                console.error('Автовоспроизведение запрещено:', e);
                // Можно показать кнопку для ручного запуска
            });
        });
    }
    // Если браузер поддерживает HLS из коробки (например, Safari)
    else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = streamUrl;
        video.addEventListener('loadedmetadata', () => {
            video.play().catch(e => {
                console.error('Автовоспроизведение запрещено:', e);
            });
        });
    }
    // Если HLS не поддерживается
    else {
        alert('Ваш браузер не поддерживает HLS-потоки.');
        video.innerHTML = '<p>Ваш браузер не поддерживает HLS-потоки. Пожалуйста, используйте современный браузер.</p>';
    }

    // Заглушка для списка участников
    const participantsList = document.getElementById('participants-list');
    if (participantsList) {
        participantsList.innerHTML = `
            <li>Участник 1</li>
            <li>Участник 2</li>
            <li>Участник 3</li>
            <li>Участник 4</li>
        `;
    }
});
