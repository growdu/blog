/**
 * 3D 封面流卡片轮播
 * 只显示 5 张卡片（当前 + 左右各 2），中间突出，两侧逐渐淡化缩小
 */
$(function() {
    $('.carousel-3d-wrapper').each(function() {
        initCarousel($(this));
    });
});

function initCarousel($wrapper) {
    var $stage = $wrapper.find('.carousel-3d-stage');
    var $container = $wrapper.find('.carousel-3d-container');
    var $cards = $wrapper.find('.carousel-3d-card');
    var $prev = $wrapper.find('.carousel-3d-nav.prev');
    var $next = $wrapper.find('.carousel-3d-nav.next');
    var $dots = $wrapper.find('.carousel-3d-dots');

    var total = $cards.length;
    if (total < 2) {
        $cards.addClass('pos-0');
        $wrapper.find('.carousel-3d-nav, .carousel-3d-dots').hide();
        return;
    }

    var current = 0;
    var autoTimer = null;
    var isDragging = false;
    var startX = 0;
    var startIdx = 0;
    var autoInterval = 4000;
    var visibleRange = 2;

    function getPositionOffset(cardIdx) {
        var diff = cardIdx - current;
        if (diff > total / 2) diff -= total;
        if (diff < -total / 2) diff += total;
        return diff;
    }

    function updatePositions() {
        $cards.each(function(i) {
            var offset = getPositionOffset(i);
            var cls = Math.abs(offset) <= visibleRange ? 'pos-' + offset : 'pos-hidden';
            $(this).attr('class', 'carousel-3d-card ' + cls);
        });
    }

    function updateIndicator() {
        if (total <= 10) {
            // 少量卡片：显示点
            $dots.find('.carousel-3d-dot').removeClass('active');
            $dots.find('.carousel-3d-dot').eq(current).addClass('active');
        } else {
            // 大量卡片：显示计数器
            $dots.html('<span class="carousel-3d-counter">' + (current + 1) + ' / ' + total + '</span>');
        }
    }

    function rotateTo(index) {
        current = ((index % total) + total) % total;
        updatePositions();
        updateIndicator();
    }

    function next() { rotateTo(current + 1); }
    function prev() { rotateTo(current - 1); }

    function startAuto() {
        stopAuto();
        if (total > 1) autoTimer = setInterval(next, autoInterval);
    }

    function stopAuto() {
        if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
    }

    // 指示器初始化
    $dots.empty();
    if (total <= 10) {
        for (var i = 0; i < total; i++) {
            $dots.append('<span class="carousel-3d-dot' + (i === 0 ? ' active' : '') + '" data-index="' + i + '"></span>');
        }
    } else {
        $dots.html('<span class="carousel-3d-counter">1 / ' + total + '</span>');
    }

    updatePositions();
    startAuto();

    $prev.on('click', function() { prev(); stopAuto(); startAuto(); });
    $next.on('click', function() { next(); stopAuto(); startAuto(); });

    $dots.on('click', '.carousel-3d-dot', function() {
        rotateTo(parseInt($(this).data('index')));
        stopAuto(); startAuto();
    });

    $(document).on('keydown.carousel3d', function(e) {
        if (!$wrapper.is(':visible')) return;
        if (e.key === 'ArrowLeft')  { prev(); stopAuto(); startAuto(); }
        if (e.key === 'ArrowRight') { next(); stopAuto(); startAuto(); }
    });

    // 鼠标拖拽
    $stage.on('mousedown touchstart', function(e) {
        isDragging = true; stopAuto();
        var ev = e.type === 'touchstart' ? e.originalEvent.touches[0] : e;
        startX = ev.clientX; startIdx = current;
    });

    $(document).on('mousemove touchmove', function(e) {
        if (!isDragging) return;
        var ev = e.type === 'touchmove' ? e.originalEvent.touches[0] : e;
        var dx = ev.clientX - startX;
        var offset = Math.round(dx / 180);
        var newIdx = ((startIdx - offset) % total + total) % total;
        if (newIdx !== current) rotateTo(newIdx);
    });

    $(document).on('mouseup touchend', function() {
        if (!isDragging) return;
        isDragging = false; startAuto();
    });

    $wrapper.on('mouseenter', stopAuto);
    $wrapper.on('mouseleave', function() { if (!isDragging) startAuto(); });

    $(window).on('resize', updatePositions);

    $cards.on('click', function(e) {
        var $link = $(this).find('a.card-link');
        if (!$link.length) return;
        if (getPositionOffset($cards.index(this)) === 0) {
            window.location.href = $link.attr('href');
        } else {
            rotateTo(($cards.index(this) + total) % total);
            stopAuto(); startAuto();
        }
    });
}
