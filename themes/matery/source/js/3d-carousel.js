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
    var visibleRange = 2; // 左右各显示 2 张

    // 计算每张卡相对于当前索引的位置偏移
    function getPositionOffset(cardIdx) {
        var diff = cardIdx - current;
        // 环形处理：让 diff 在 [-total/2, total/2] 范围内
        if (diff > total / 2) diff -= total;
        if (diff < -total / 2) diff += total;
        return diff;
    }

    // 更新所有卡片的 position class
    function updatePositions() {
        $cards.each(function(i) {
            var offset = getPositionOffset(i);
            var cls;
            if (Math.abs(offset) <= visibleRange) {
                cls = 'pos-' + offset;
            } else {
                cls = 'pos-hidden';
            }
            $(this).attr('class', 'carousel-3d-card ' + cls);
        });
    }

    // 旋转到指定索引
    function rotateTo(index) {
        current = ((index % total) + total) % total;
        updatePositions();

        $dots.find('.carousel-3d-dot').removeClass('active');
        $dots.find('.carousel-3d-dot').eq(current).addClass('active');
    }

    function next() { rotateTo(current + 1); }
    function prev() { rotateTo(current - 1); }

    function startAuto() {
        stopAuto();
        if (total > 1) {
            autoTimer = setInterval(next, autoInterval);
        }
    }

    function stopAuto() {
        if (autoTimer) {
            clearInterval(autoTimer);
            autoTimer = null;
        }
    }

    // 创建指示点
    $dots.empty();
    for (var i = 0; i < total; i++) {
        $dots.append('<span class="carousel-3d-dot' + (i === 0 ? ' active' : '') + '" data-index="' + i + '"></span>');
    }

    // 初始化
    updatePositions();
    startAuto();

    // 导航按钮
    $prev.on('click', function() { prev(); stopAuto(); startAuto(); });
    $next.on('click', function() { next(); stopAuto(); startAuto(); });

    // 指示点
    $dots.on('click', '.carousel-3d-dot', function() {
        rotateTo(parseInt($(this).data('index')));
        stopAuto();
        startAuto();
    });

    // 键盘导航
    $(document).on('keydown.carousel3d', function(e) {
        if (!$wrapper.is(':visible')) return;
        if (e.key === 'ArrowLeft')  { prev(); stopAuto(); startAuto(); }
        if (e.key === 'ArrowRight') { next(); stopAuto(); startAuto(); }
    });

    // 鼠标拖拽
    $stage.on('mousedown touchstart', function(e) {
        isDragging = true;
        stopAuto();
        var ev = e.type === 'touchstart' ? e.originalEvent.touches[0] : e;
        startX = ev.clientX;
        startIdx = current;
    });

    $(document).on('mousemove touchmove', function(e) {
        if (!isDragging) return;
        var ev = e.type === 'touchmove' ? e.originalEvent.touches[0] : e;
        var dx = ev.clientX - startX;
        var sensitivity = 180;
        var offset = Math.round(dx / sensitivity);
        var newIdx = ((startIdx - offset) % total + total) % total;
        if (newIdx !== current) {
            rotateTo(newIdx);
        }
    });

    $(document).on('mouseup touchend', function() {
        if (!isDragging) return;
        isDragging = false;
        startAuto();
    });

    // 悬停暂停
    $wrapper.on('mouseenter', stopAuto);
    $wrapper.on('mouseleave', function() {
        if (!isDragging) startAuto();
    });

    // 窗口大小变化
    $(window).on('resize', function() {
        updatePositions();
    });

    // 卡片点击：中间卡片直接跳转，侧边卡片先旋转到中间
    $cards.on('click', function(e) {
        var $link = $(this).find('a.card-link');
        if (!$link.length) return;

        var offset = getPositionOffset($cards.index(this));
        if (offset === 0) {
            // 当前激活卡片，直接跳转
            window.location.href = $link.attr('href');
        } else {
            // 旋转到该卡片
            rotateTo(($cards.index(this) + total) % total);
            stopAuto();
            startAuto();
        }
    });
}
