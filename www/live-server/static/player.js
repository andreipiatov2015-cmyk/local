document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, доступна ли библиотека Hls
    if (typeof Hls === 'undefined') {
        console.error('Hls.js не загружен!');
        return;
    }

    var video = document.getElementById('video');
    
    // Проверяем, поддерживается ли HLS в текущем браузере
    if (Hls.isSupported()) {
        var hls = new Hls();

        // Укажите URL вашего HLS-потока (файл .m3u8)
        hls.loadSource('http://192.168.31.18:8080/hls/test.m3u8');

        // Подключаем HLS к видеоплееру
        hls.attachMedia(video);

        // Запускаем воспроизведение, когда поток готов
        hls.on(Hls.Events.MANIFEST_PARSED, function() {
            video.play().catch(e => {
                console.error('Автовоспроизведение запрещено:', e);
                // Можно показать кнопку для ручного запуска
            });
        });
    }
    // Если браузер поддерживает HLS из коробки (например, Safari)
    else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = 'http://192.168.31.18:8080/hls/test.m3u8';
        video.addEventListener('loadedmetadata', function() {
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
    document.getElementById('participants-list').innerHTML = `
        <li>Участник 1</li>
        <li>Участник 2</li>
        <li>Участник 3</li>
        <li>Участник 4</li>
    `;
});