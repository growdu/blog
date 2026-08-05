/**
 * 智能摘要生成器
 * 从文章内容中提取第一段有意义的中文描述作为摘要
 */
hexo.extend.helper.register('smart_summary', function(post) {
    // 1. 优先使用 front matter 中的 description
    if (post.description && post.description.trim().length > 0) {
        return post.description.trim();
    }

    // 2. 使用 front matter 中的 summary
    if (post.summary && post.summary.trim().length > 0) {
        return post.summary.trim();
    }

    // 3. 使用 hexo 自动生成的 excerpt（如果用了 <!-- more -->）
    var raw = post.raw || post.content || '';
    if (!raw) return '';

    // 4. 智能提取第一段正文
    var lines = raw.split('\n');
    var paragraph = '';
    var inCodeBlock = false;
    var inTable = false;
    var inFrontMatter = false;
    var frontMatterCount = 0;

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();

        // 检测 front matter 边界
        if (line === '---') {
            frontMatterCount++;
            if (frontMatterCount === 1) {
                inFrontMatter = true;
                continue;
            } else if (inFrontMatter) {
                inFrontMatter = false;
                continue;
            }
        }

        // 跳过 front matter 内容
        if (inFrontMatter) continue;

        // 跳过代码块
        if (line.startsWith('```') || line.startsWith('~~~')) {
            inCodeBlock = !inCodeBlock;
            continue;
        }
        if (inCodeBlock) continue;

        // 跳过表格
        if (line.startsWith('|')) {
            inTable = true;
            continue;
        } else if (inTable && !line.startsWith('|')) {
            inTable = false;
        }
        if (inTable) continue;

        // 跳过分隔线
        if (/^[-*=_]{3,}$/.test(line)) continue;

        // 跳过标题行
        if (/^#{1,6}\s/.test(line)) continue;

        // 跳过元数据行（如"编写人"、"编写内容"等中文元数据表头）
        if (/^(编写人|编写内容|编写时间|作者|日期|时间|版本|修订|审核|批准)[\s|：:]/.test(line)) continue;

        // 跳过纯链接、图片行
        if (/^[!\[].*\]\(.*\)$/.test(line)) continue;
        if (/^<.*>$/.test(line)) continue;

        // 跳过引用标记（只取引用内容）
        if (line.startsWith('>')) {
            line = line.replace(/^>\s*/, '');
        }

        // 收集非空行作为段落
        if (line.length > 0) {
            paragraph += line;
            // 当累积到足够长度时停止
            if (paragraph.length >= 60) break;
        } else if (paragraph.length > 0) {
            // 遇到空行且已有内容，表示段落结束
            break;
        }
    }

    // 5. 清理 markdown 格式
    paragraph = paragraph
        .replace(/\*\*(.+?)\*\*/g, '$1')      // 粗体
        .replace(/__(.+?)__/g, '$1')           // 粗体
        .replace(/\*(.+?)\*/g, '$1')            // 斜体
        .replace(/_(.+?)_/g, '$1')              // 斜体
        .replace(/~~(.+?)~~/g, '$1')            // 删除线
        .replace(/`(.+?)`/g, '$1')              // 行内代码
        .replace(/\[(.+?)\]\(.+?\)/g, '$1')     // 链接
        .replace(/!\[.*?\]\(.+?\)/g, '')        // 图片
        .replace(/^#{1,6}\s*/g, '')             // 标题标记
        .replace(/^>\s*/g, '')                  // 引用标记
        .replace(/^\s*[-*+]\s+/g, '')           // 列表标记
        .replace(/^\s*\d+\.\s+/g, '')           // 有序列表
        .replace(/\n/g, ' ')                    // 换行变空格
        .replace(/\s+/g, ' ')                   // 合并空格
        .trim();

    // 6. 截断到合适长度
    if (paragraph.length > 200) {
        // 尝试在句号处截断
        var cutPoint = paragraph.lastIndexOf('。', 200);
        if (cutPoint > 100) {
            paragraph = paragraph.substring(0, cutPoint + 1);
        } else {
            paragraph = paragraph.substring(0, 200) + '…';
        }
    }

    return paragraph;
});
