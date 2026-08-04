/**
 * 3D 旋转卡片轮播
 * 将文章卡片排列成 3D 圆形，支持自动旋转、拖拽、导航
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
        // 只有一张卡片时直接显示，不需要轮播
        $cards.addClass('active');
        $wrapper.find('.carousel-3d-nav, .carousel-3d-dots').hide();
        return;
    }

    var current = 0;
    var angleStep = 360 / total;
    var radius = 380;
    var autoTimer = null;
    var isDragging = false;
    var startX = 0;
    var startAngle = 0;
    var autoInterval = 4000;

    // 响应式半径
    function updateRadius() {
        var w = $(window).width();
        if (w < 480) radius = 220;
        else if (w < 768) radius = 280;
        else radius = 380;
    }

    // 排列卡片
    function arrangeCards() {
        updateRadius();
        $cards.each(function(i) {
            var angle = angleStep * i;
            $(this).css('transform', 'rotateY(' + angle + 'deg) translateZ(' + radius + 'px)');
        });
    }

    // 旋转到指定索引
    function rotateTo(index) {
        current = ((index % total) + total) % total;
        var angle = -angleStep * current;
        $container.css('transform', 'rotateY(' + angle + 'deg)');

        $cards.removeClass('active');
        $cards.eq(current).addClass('active');

        $dots.find('.carousel-3d-dot').removeClass('active');
        $dots.find('.carousel-3d-dot').eq(current).addClass('active');
    }

    // 下一张
    function next() {
        rotateTo(current + 1);
    }

    // 上一张
    function prev() {
        rotateTo(current - 1);
    }

    // 自动播放
    function startAuto() {
        stopAuto();
        autoTimer = setInterval(next, autoInterval);
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
    arrangeCards();
    rotateTo(0);
    startAuto();

    // 导航按钮
    $prev.on('click', function() {
        prev();
        stopAuto();
        startAuto();
    });

    $next.on('click', function() {
        next();
        stopAuto();
        startAuto();
    });

    // 指示点点击
    $dots.on('click', '.carousel-3d-dot', function() {
        var idx = $(this).data('index');
        rotateTo(idx);
        stopAuto();
        startAuto();
    });

    // 键盘导航
    $(document).on('keydown.carousel3d', function(e) {
        if (!$wrapper.is(':visible')) return;
        if (e.key === 'ArrowLeft') {
            prev();
            stopAuto();
            startAuto();
        } else if (e.key === 'ArrowRight') {
            next();
            stopAuto();
            startAuto();
        }
    });

    // 鼠标拖拽
    $stage.on('mousedown touchstart', function(e) {
        isDragging = true;
        stopAuto();
        var ev = e.type === 'touchstart' ? e.originalEvent.touches[0] : e;
        startX = ev.clientX;
        startAngle = current;
        $container.css('transition', 'none');
    });

    $(document).on('mousemove touchmove', function(e) {
        if (!isDragging) return;
        var ev = e.type === 'touchmove' ? e.originalEvent.touches[0] : e;
        var dx = ev.clientX - startX;
        var sensitivity = total > 6 ? 200 : 300;
        var offset = Math.round(dx / sensitivity);
        var newIndex = startAngle + offset;
        var angle = -angleStep * newIndex;
        $container.css('transform', 'rotateY(' + angle + 'deg)');
    });

    $(document).on('mouseup touchend', function() {
        if (!isDragging) return;
        isDragging = false;

        var currentAngle = parseFloat($container.css('transform').split(',')[4]) || 0;
        // 从矩阵中提取角度
        var style = $container.attr('style') || '';
        var match = style.match(/rotateY\(([-\d.]+)deg\)/);
        if (match) {
            currentAngle = parseFloat(match[1]);
        }

        var rawIndex = -currentAngle / angleStep;
        var snapIndex = Math.round(rawIndex);
        $container.css('transition', 'transform 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)');
        rotateTo(snapIndex);
        startAuto();
    });

    // 鼠标悬停暂停
    $wrapper.on('mouseenter', function() {
        stopAuto();
    });

    $wrapper.on('mouseleave', function() {
        if (!isDragging) {
            startAuto();
        }
    });

    // 窗口大小改变时重新排列
    var resizeTimer;
    $(window).on('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            arrangeCards();
            rotateTo(current);
        }, 200);
    });

    // 卡片点击跳转
    $cards.on('click', function(e) {
        var $link = $(this).find('a.card-link');
        if ($link.length) {
            // 如果点击的是当前激活的卡片，直接跳转
            if ($(this).hasClass('active')) {
                window.location.href = $link.attr('href');
            } else {
                // 否则先旋转到该卡片
                var idx = $cards.index(this);
                rotateTo(idx);
                stopAuto();
                startAuto();
            }
        }
    });
}
